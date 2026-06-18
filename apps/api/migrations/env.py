"""Alembic environment.

The URL and target metadata come from the application, not from ``alembic.ini``: the URL
is the app's ``database_url`` setting (so migrations hit the same EU-region Postgres the
service does, with no secret in a committed file), and ``target_metadata`` is the live
``Base.metadata`` with every model imported — that import is what makes autogenerate see
the schema. ``render_as_batch`` is on so the migrations also apply on SQLite, which can't
ALTER columns in place.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import AsyncEngine

from app.config import get_settings
from app.db.base import Base
from app.db.session import create_engine

# Importing the models package registers every mapper on Base.metadata.
import app.db.models  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

_DATABASE_URL = get_settings().database_url


def _configure(connection) -> None:  # noqa: ANN001
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=connection.dialect.name == "sqlite",
        compare_type=True,
        compare_server_default=True,
    )


def run_migrations_offline() -> None:
    context.configure(
        url=_DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=_DATABASE_URL.startswith("sqlite"),
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def _run_async_migrations() -> None:
    engine: AsyncEngine = create_engine(_DATABASE_URL)
    async with engine.connect() as connection:
        await connection.run_sync(lambda sync_conn: _do_run(sync_conn))
    await engine.dispose()


def _do_run(sync_connection) -> None:  # noqa: ANN001
    _configure(sync_connection)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    asyncio.run(_run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
