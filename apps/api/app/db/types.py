"""Column types and mixins that keep one schema portable across two backends.

The product runs on Postgres (EU residency, the price-history data lake), but the test
suite runs on in-memory SQLite — no Docker in this environment. These types are the seam
that lets the *same* models target both:

- ``GUID`` stores ``uuid.UUID`` as Postgres native ``UUID`` and as a 32-char hex ``CHAR``
  on SQLite, so id semantics are identical and tests don't need Postgres.
- ``utcnow`` timestamps are always stored timezone-aware in UTC; ``DateTime(timezone=True)``
  maps to ``timestamptz`` on Postgres and a naive column on SQLite, which is why the value
  is normalized to UTC in Python rather than trusted to the column.

Anything genuinely Postgres-only (JSONB, partial indexes) would also live behind this
module; the current schema deliberately uses portable types so nothing is lost on SQLite.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import CHAR, DateTime, types
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.engine import Dialect


class GUID(types.TypeDecorator):
    """Platform-independent UUID: native ``UUID`` on Postgres, ``CHAR(32)`` elsewhere."""

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(32))

    def process_bind_param(self, value: uuid.UUID | str | None, dialect: Dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
        if isinstance(value, uuid.UUID):
            return value.hex
        return uuid.UUID(str(value)).hex

    def process_result_value(self, value: str | uuid.UUID | None, dialect: Dialect):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(value)


def new_uuid() -> uuid.UUID:
    return uuid.uuid4()


def utcnow() -> datetime:
    """Timezone-aware UTC ``now`` — the only timestamp factory models should use."""
    return datetime.now(timezone.utc)


# Aliased so models read ``Timestamp`` and the timezone intent is stated once, here.
Timestamp = DateTime(timezone=True)
