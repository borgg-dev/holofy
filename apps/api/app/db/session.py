"""Async engine and session factory.

One engine per process (it owns the connection pool), one ``async_sessionmaker`` bound to
it. Repositories and request handlers take a ``AsyncSession``; they never touch the engine.

SQLite needs ``check_same_thread=False`` and, for the in-memory test database, a
``StaticPool`` so every session shares the single in-memory database rather than each
connection getting its own empty one — that detail is what lets the test suite create the
schema once and have the repositories see it. Postgres uses the default pool.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool


def create_engine(database_url: str, *, echo: bool = False) -> AsyncEngine:
    if database_url.startswith("sqlite"):
        engine = create_async_engine(
            database_url,
            echo=echo,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        # SQLite ships with FK enforcement off per connection; without this the running app
        # (unlike Postgres) silently ignores ON DELETE cascades and FK constraints.
        @event.listens_for(engine.sync_engine, "connect")
        def _enable_sqlite_foreign_keys(dbapi_connection, _record):  # noqa: ANN001
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        return engine
    return create_async_engine(database_url, echo=echo, pool_pre_ping=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


async def session_scope(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Yield a session that commits on success and rolls back on error.

    The unit-of-work boundary for a request/task: the caller does its work, and the
    transaction is committed or rolled back here rather than at scattered call sites.
    """
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
