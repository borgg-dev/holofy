"""A cached € price point per card — persisting the daily snapshots that become our own
price history.

The architecture (§4) calls for persisting the daily/hourly aggregator snapshots to
Postgres so that, over time, Holofy owns a price history independent of any single feed —
which both powers value-over-time and de-risks a feed disappearing. Each row is one
``(card, source, basis, observed_at)`` reading with its provenance and an explicit
freshness stamp, so a consumer can prefer a fresher point and know which feed it came from.

This is market reference data, not personal data: it is keyed on ``Card``, shared across
users, and not erased on a user delete.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import GUID, Timestamp, new_uuid, utcnow

if TYPE_CHECKING:
    from app.db.models.card import Card


class PriceObservation(Base):
    __tablename__ = "price_observations"
    __table_args__ = (
        # One reading per card/source/basis per observation instant — re-ingesting the
        # same daily snapshot is idempotent rather than duplicating history.
        UniqueConstraint("card_id", "source", "basis", "observed_at"),
        CheckConstraint("value_eur >= 0", name="value_non_negative"),
        # The hot read is "latest point for this card": a (card_id, observed_at) composite
        # lets the engine read just this card's slice in index order (scanned from the
        # newest end) instead of its whole history.
        Index("ix_price_observations_card_id_observed_at", "card_id", "observed_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)

    # No standalone index on ``card_id``: the composite ``(card_id, observed_at)`` below has
    # it as its leading column, so a lone index would be redundant write overhead.
    card_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("cards.id", ondelete="CASCADE")
    )

    value_eur: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="EUR")

    source: Mapped[str] = mapped_column(String(24))
    basis: Mapped[str] = mapped_column(String(16))

    # When the source reported the price (its freshness), distinct from when we ingested it.
    observed_at: Mapped[datetime] = mapped_column(Timestamp)
    ingested_at: Mapped[datetime] = mapped_column(Timestamp, default=utcnow)

    card: Mapped["Card"] = relationship(back_populates="price_observations")
