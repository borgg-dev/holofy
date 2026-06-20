from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.testclient import TestClient

from app.auth.dev_token import mint_dev_token
from app.config import (
    AuthBackend,
    AuthenticityBackend,
    CaptureStorageBackend,
    CatalogBackend,
    DataLakeBackend,
    GradingBackend,
    PricingBackend,
    RateLimitBackend,
    RecognitionBackend,
    Settings,
)
from app.db.base import Base
from app.db.session import create_engine, create_session_factory
from app.main import create_app

# In-memory SQLite — the whole persistence suite runs with no Postgres and no Docker.
_TEST_DATABASE_URL = "sqlite+aiosqlite://"
_DEV_SECRET = "test-secret"


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    """A session over a fresh in-memory schema, created per test from the ORM metadata.

    SQLite ignores ``ON DELETE CASCADE`` unless the ``foreign_keys`` pragma is on, so it is
    enabled on every connection via an event listener — the erasure tests depend on the
    cascade firing, exactly as Postgres would.
    """
    engine = create_engine(_TEST_DATABASE_URL)

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _record):  # noqa: ANN001, ANN202
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = create_session_factory(engine)
    async with session_factory() as test_session:
        yield test_session

    await engine.dispose()


@pytest.fixture
def settings() -> Settings:
    # Every backend pinned to its hermetic value and an in-memory database — the API suite
    # runs with no network, no keys, and no Postgres. These are pinned explicitly (not left to
    # config defaults) precisely because the *production* defaults are now the real providers
    # (in-house recognition, TCGdex catalog/pricing); the suite must stay offline regardless.
    # The dev secret is fixed so the test harness can mint tokens.
    return Settings(
        recognition_provider=RecognitionBackend.MOCK,
        catalog_provider=CatalogBackend.INMEMORY,
        pricing_provider=PricingBackend.MOCK,
        grading_provider=GradingBackend.MOCK,
        authenticity_provider=AuthenticityBackend.MOCK,
        capture_storage=CaptureStorageBackend.MOCK,
        datalake_sink=DataLakeBackend.MOCK,
        rate_limit_provider=RateLimitBackend.MEMORY,
        # The harness mints dev tokens (mint_dev_token); pin that bearer backend explicitly,
        # since the production default is now the password-issued session token.
        auth_provider=AuthBackend.DEV_TOKEN,
        database_url=_TEST_DATABASE_URL,
        auth_dev_secret=_DEV_SECRET,
        log_json=False,
        cors_allow_origins=["https://app.holofy.test"],
        # The quota tests assert the limit is enforced at the 8/day freemium tier; pin it here
        # so they're independent of the (now generous, beta-time) production default.
        free_tier_daily_scans=8,
    )


@pytest.fixture
def client(settings: Settings):
    with TestClient(create_app(settings)) as test_client:
        # The lifespan built the app's engine on the TestClient's portal loop; create the
        # schema on that same engine/loop so the API routes and their repositories see the
        # one in-memory database. ``portal.call`` runs the coroutine on that loop.
        app = test_client.app
        engine = app.state.db_engine

        async def _create_schema() -> None:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

        test_client.portal.call(_create_schema)
        yield test_client


def auth_header(subject: str = "collector-1") -> dict[str, str]:
    """A bearer header for a deterministic test user — the harness's stand-in for login."""
    return {"Authorization": f"Bearer {mint_dev_token(subject, secret=_DEV_SECRET)}"}
