"""``PricingProvider`` backed by the open TCGdex catalog.

Adapts the shared ``TcgdexClient`` to the provider Protocol: it translates the client's
domain exceptions into the API's error model and its ``CardmarketPrice`` into the
transport-neutral ``PriceQuote``. No key required (ADR 0001). In production this provider
fronts a Redis/Postgres cache rather than calling TCGdex on every scan; here it is the
real-data path the mock substitutes for offline.
"""

from __future__ import annotations

import httpx

from app.core.errors import (
    CardNotFoundError,
    PriceUnavailableError,
    UpstreamUnavailableError,
)
from app.providers.pricing.tcgdex import (
    CardmarketPrice,
    CardNotFound,
    PriceUnavailable,
    TcgdexClient,
)
from app.schemas.cards import PriceQuote

_SOURCE = "cardmarket_via_tcgdex"


def _to_quote(price: CardmarketPrice) -> PriceQuote:
    basis = "trend" if price.trend_eur is not None else "avg30"
    return PriceQuote(
        canonical_id=price.card_id,
        value=price.display_value,
        basis=basis,
        low=price.low_eur,
        avg30=price.avg30_eur,
        source=_SOURCE,
        as_of=price.updated,
        age_hours=price.age_hours,
        listing_url=price.listing_url,
    )


class TcgdexPricingProvider:
    def __init__(self, client: TcgdexClient) -> None:
        self._client = client

    async def price(
        self, canonical_id: str, *, name: str | None = None, collector_number: str | None = None
    ) -> PriceQuote:
        # TCGdex keys by the same canonical id the recognizer uses, so the name/number fallback key
        # is unused here — accepted only to satisfy the shared seam.
        try:
            reading = await self._client.fetch_cardmarket_price(canonical_id)
        except CardNotFound as exc:
            raise CardNotFoundError(
                "Card not found in catalog.",
                details={"canonical_id": canonical_id},
            ) from exc
        except PriceUnavailable as exc:
            raise PriceUnavailableError(
                "No Cardmarket pricing for this card.",
                details={"canonical_id": canonical_id},
            ) from exc
        except httpx.HTTPError as exc:
            raise UpstreamUnavailableError(
                "Pricing source is unavailable.",
                details={"canonical_id": canonical_id},
            ) from exc
        return _to_quote(reading)
