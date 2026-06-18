from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.testclient import TestClient

from app.config import PricingBackend, RecognitionBackend, Settings
from app.db.base import Base
from app.db.session import create_engine, create_session_factory
from app.main import create_app

# In-memory SQLite — the whole persistence suite runs with no Postgres and no Docker.
_TEST_DATABASE_URL = "sqlite+aiosqlite://"


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
    # Fully mocked backends — the API suite must run with no network and no keys.
    return Settings(
        recognition_provider=RecognitionBackend.MOCK,
        pricing_provider=PricingBackend.MOCK,
        log_json=False,
        cors_allow_origins=["https://app.holofy.test"],
    )


@pytest.fixture
def client(settings: Settings):
    with TestClient(create_app(settings)) as test_client:
        yield test_client
