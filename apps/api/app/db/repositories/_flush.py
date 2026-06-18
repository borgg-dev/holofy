"""Flush helper that maps a driver constraint violation to a domain error.

A constraint collision (a duplicate unique key, a failed check, an orphaned foreign key) is a
client-meaningful conflict, not an internal fault — but SQLAlchemy surfaces it as a raw
``IntegrityError`` that would otherwise reach the catch-all handler as a 500. The write
repositories flush through here so the violation lands as a typed ``ConstraintViolationError``
(409) in the one error envelope the client parses, with the constraint name (when the driver
exposes it) for context — never the raw SQL.
"""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConstraintViolationError


async def flush_or_conflict(session: AsyncSession) -> None:
    """Flush pending writes, re-raising a constraint violation as a typed 409.

    The session is rolled back to a usable state before the domain error propagates, so the
    request's transaction unwinds cleanly rather than leaving a poisoned session behind.
    """
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise ConstraintViolationError(
            "This change conflicts with existing data.",
            details=_constraint_detail(exc),
        ) from exc


def _constraint_detail(exc: IntegrityError) -> dict[str, object]:
    """The constraint name from the driver, when it exposes one — never the raw statement."""
    name = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
    return {"constraint": name} if name else {}
