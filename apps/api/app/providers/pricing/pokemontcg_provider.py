"""``PricingProvider`` backed by pokémontcg.io — native EUR *and* USD, with a TCGdex fallback.

Maps the client's dual-market reading into the transport-neutral ``PriceQuote``: the EUR (Cardmarket)
figure stays ``value``/``currency`` so the EUR-denominated portfolio is unchanged, and the native US
(TCGplayer) figure rides along as ``usd_value`` for an honest USD view. When pokémontcg.io can't
match a card (its ids don't cover the whole catalog), it defers to a fallback provider — the TCGdex
Cardmarket path — so native-USD is added for the ~85% it covers without losing EUR coverage on the
rest. A card neither source carries is a long-tail "no comp", surfaced honestly, never an error.
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx

from app.core.errors import PriceUnavailableError, UpstreamUnavailableError
from app.providers.base import PricingProvider
from app.providers.pricing.pokemontcg import (
    PokemonTcgClient,
    PokemonTcgPrice,
    PokemonTcgPriceUnavailable,
)
from app.schemas.cards import PriceQuote

_SOURCE = "cardmarket+tcgplayer_via_pokemontcg"


def _quote(canonical_id: str, p: PokemonTcgPrice) -> PriceQuote:
    value = p.eur_trend or p.eur_low  # lead with the smoothed trend; fall back to the low comp
    age_hours = max(0.0, (datetime.now(UTC) - p.updated).total_seconds() / 3600.0)
    return PriceQuote(
        canonical_id=canonical_id,
        currency="EUR",
        value=value,
        basis="trend" if p.eur_trend is not None else ("low" if p.eur_low is not None else "usd"),
        low=p.eur_low,
        avg30=p.eur_avg30,
        usd_value=p.usd_market,
        source=_SOURCE,
        as_of=p.updated,
        age_hours=age_hours,
        listing_url=p.tcgplayer_url,
    )


class PokemonTcgPricingProvider:
    def __init__(self, client: PokemonTcgClient, *, fallback: PricingProvider | None = None) -> None:
        self._client = client
        self._fallback = fallback

    async def price(
        self, canonical_id: str, *, name: str | None = None, collector_number: str | None = None
    ) -> PriceQuote:
        try:
            reading = await self._client.fetch(canonical_id, name=name, collector_number=collector_number)
            return _quote(canonical_id, reading)
        except PokemonTcgPriceUnavailable:
            # No match / no price here — try the fallback (TCGdex EUR) before giving up, so coverage
            # never drops below the EUR-only baseline.
            if self._fallback is not None:
                return await self._fallback.price(
                    canonical_id, name=name, collector_number=collector_number
                )
            raise PriceUnavailableError(
                "No market pricing for this card.", details={"canonical_id": canonical_id}
            ) from None
        except httpx.HTTPError as exc:
            if self._fallback is not None:
                return await self._fallback.price(
                    canonical_id, name=name, collector_number=collector_number
                )
            raise UpstreamUnavailableError(
                "Pricing source is unavailable.", details={"canonical_id": canonical_id}
            ) from exc
