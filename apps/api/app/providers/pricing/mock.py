"""Offline pricing provider for tests and keyless local runs.

Returns fixed € quotes for the recognition mock's canonical ids; the ~31× spread between
the two Emberwyrm Sovereign printings mirrors the real variant-mis-pricing risk the
confirm step guards against. Unknown ids raise ``PriceUnavailableError`` — the same domain
signal the real provider raises for a long-tail card — so callers exercise that branch
offline.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from app.core.errors import PriceUnavailableError
from app.schemas.cards import PriceQuote

_SOURCE = "mock"

# canonical_id → (trend, avg30, low)
_PRICES: dict[str, tuple[Decimal, Decimal, Decimal]] = {
    "origins-12": (Decimal("757.10"), Decimal("529.99"), Decimal("100.00")),
    "echo-12": (Decimal("24.50"), Decimal("22.10"), Decimal("9.00")),
    "origins-8": (Decimal("289.00"), Decimal("271.40"), Decimal("120.00")),
}


class MockPricingProvider:
    """Static € quotes with a fixed ``as_of`` so freshness assertions are deterministic."""

    def __init__(self, *, as_of: datetime | None = None) -> None:
        self._as_of = as_of or datetime(2026, 6, 18, tzinfo=timezone.utc)

    async def price(
        self, canonical_id: str, *, name: str | None = None, collector_number: str | None = None
    ) -> PriceQuote:
        priced = _PRICES.get(canonical_id)
        if priced is None:
            raise PriceUnavailableError(
                "No pricing for this card.",
                details={"canonical_id": canonical_id},
            )
        trend, avg30, low = priced
        return PriceQuote(
            canonical_id=canonical_id,
            value=trend,
            basis="trend",
            low=low,
            avg30=avg30,
            source=_SOURCE,
            as_of=self._as_of,
            age_hours=0.0,
        )
