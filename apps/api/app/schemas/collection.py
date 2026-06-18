"""Request/response contract for the user's collection.

A collection item is *this collector's copy* of a catalog card: its condition and quantity,
optional cost basis, and — on read — the current € valuation derived from the latest price.
Adding is keyed by the card's ``canonical_id`` (what a scan or manual lookup yields), so the
client never has to know our internal card uuid.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.db.models.enums import CardCondition
from app.schemas.cards import CardIdentity


class AddCollectionItemRequest(BaseModel):
    canonical_id: str = Field(min_length=1)
    condition: CardCondition = CardCondition.NEAR_MINT
    quantity: int = Field(default=1, ge=1)
    # What the collector paid, for the cost-basis vs current-value delta. Non-negative €.
    acquired_price_eur: Decimal | None = Field(default=None, ge=0)
    acquired_on: date | None = None


class CollectionItemValuation(BaseModel):
    """One holding with its current € valuation.

    ``unit_value_eur`` is the per-copy price at ``valued_at``; ``line_value_eur`` multiplies
    by quantity. Both are ``None`` for a long-tail card with no price yet — surfaced honestly
    rather than valued at zero.
    """

    id: str
    card: CardIdentity
    condition: CardCondition
    quantity: int
    acquired_price_eur: Decimal | None
    acquired_on: date | None
    unit_value_eur: Decimal | None
    line_value_eur: Decimal | None
    valued_at: datetime | None
    price_source: str | None


class CollectionResponse(BaseModel):
    items: list[CollectionItemValuation]
    total_value_eur: Decimal
    currency: str = "EUR"
