"""Persistence layer: ORM models, async session plumbing, and repositories.

Postgres is the production target (EU residency, the price-history data lake); the test
suite runs the same models on in-memory SQLite. Portability lives in ``types`` (the
GUID/timestamp seam) and ``base`` (the naming convention that keeps migrations stable
across both backends).
"""

from __future__ import annotations

from app.db.base import Base

__all__ = ["Base"]
