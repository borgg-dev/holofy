"""The pokémontcg.io pricing path: dual-market extraction, id→name fallback, and the EUR fallback.

Network is mocked via ``httpx.MockTransport`` so the suite stays offline and deterministic. The
behaviours pinned are the ones the multi-market pricing turns on: a card yields both a native EUR
(Cardmarket) ``value`` and a native USD (TCGplayer) ``usd_value``; an id miss recovers by name +
number; and when pokémontcg.io has nothing, the provider defers to the TCGdex EUR fallback so EUR
coverage never regresses.
"""

from __future__ import annotations

from decimal import Decimal

import httpx
import pytest

from app.providers.pricing.pokemontcg import PokemonTcgClient, PokemonTcgPriceUnavailable
from app.providers.pricing.pokemontcg_provider import PokemonTcgPricingProvider
from app.schemas.cards import PriceQuote


def _card(card_id: str, *, number: str = "4", usd: float | None = 630.39, eur: float | None = 265.0) -> dict:
    card: dict = {"id": card_id, "name": "Charizard", "number": number}
    if usd is not None:
        card["tcgplayer"] = {
            "url": "https://tcgplayer.com/x",
            "updatedAt": "2026/06/23",
            "prices": {"holofoil": {"low": 534.99, "mid": 699.99, "market": usd}},
        }
    if eur is not None:
        card["cardmarket"] = {"updatedAt": "2026/06/23", "prices": {"trendPrice": eur, "avg30": 244.9, "lowPrice": 180.0}}
    return card


def _client(handler) -> PokemonTcgClient:  # noqa: ANN001
    return PokemonTcgClient(client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))


@pytest.mark.asyncio
async def test_extracts_both_markets_by_id() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path.endswith("/cards/base1-4")
        return httpx.Response(200, json={"data": _card("base1-4")})

    price = await _client(handler).fetch("base1-4")
    assert price.eur_trend == Decimal("265.0")
    assert price.usd_market == Decimal("630.39")
    assert price.eur_low == Decimal("180.0")


@pytest.mark.asyncio
async def test_falls_back_to_name_number_search_on_id_miss() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path.endswith("/cards/zzz-9"):
            return httpx.Response(404)  # id miss
        # name+number search
        assert "name:" in req.url.params.get("q", "")
        return httpx.Response(200, json={"data": [_card("base1-4", number="4")]})

    price = await _client(handler).fetch("zzz-9", name="Charizard", collector_number="4/102")
    assert price.usd_market == Decimal("630.39")


@pytest.mark.asyncio
async def test_no_match_raises_unavailable() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        if "/cards/" in req.url.path and not req.url.path.endswith("/cards"):
            return httpx.Response(404)
        return httpx.Response(200, json={"data": []})

    with pytest.raises(PokemonTcgPriceUnavailable):
        await _client(handler).fetch("zzz-9", name="Nope", collector_number="1/1")


@pytest.mark.asyncio
async def test_provider_maps_to_quote_with_native_usd() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": _card("base1-4")})

    provider = PokemonTcgPricingProvider(_client(handler))
    quote = await provider.price("base1-4", name="Charizard", collector_number="4/102")
    assert quote.currency == "EUR"
    assert quote.value == Decimal("265.0")  # native Cardmarket EUR (portfolio totals on this)
    assert quote.usd_value == Decimal("630.39")  # native TCGplayer USD (honest USD view)
    assert "pokemontcg" in quote.source


@pytest.mark.asyncio
async def test_provider_defers_to_fallback_when_pokemontcg_has_nothing() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        if "/cards/" in req.url.path and not req.url.path.endswith("/cards"):
            return httpx.Response(404)
        return httpx.Response(200, json={"data": []})

    class _Fallback:
        async def price(self, canonical_id, *, name=None, collector_number=None):  # noqa: ANN001
            return PriceQuote(
                canonical_id=canonical_id, value=Decimal("9.99"), basis="trend",
                source="tcgdex", as_of=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
                age_hours=1.0,
            )

    provider = PokemonTcgPricingProvider(_client(handler), fallback=_Fallback())
    quote = await provider.price("missing-1", name="Ghost", collector_number="1/1")
    assert quote.source == "tcgdex"
    assert quote.value == Decimal("9.99")
    assert quote.usd_value is None  # fallback is EUR-only
