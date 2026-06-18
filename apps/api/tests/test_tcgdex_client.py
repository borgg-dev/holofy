"""Coverage for the shared TCGdex client and its provider adapter.

Network is mocked via ``httpx.MockTransport`` (the spike pattern) so the suite is
hermetic. These pin the branching the client reasons about — the trend→avg30 fallback,
null-price and not-found degradation, the URL it builds — and that the adapter maps each
domain condition onto the right API error.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import httpx
import pytest

from app.core.errors import (
    CardNotFoundError,
    PriceUnavailableError,
    UpstreamUnavailableError,
)
from app.providers.pricing.tcgdex import (
    CardNotFound,
    PriceUnavailable,
    TcgdexClient,
    to_decimal,
)
from app.providers.pricing.tcgdex_provider import TcgdexPricingProvider


def _client(handler) -> TcgdexClient:
    transport = httpx.MockTransport(handler)
    return TcgdexClient(client=httpx.AsyncClient(transport=transport))


def _card_payload(pricing: dict | None) -> dict:
    card: dict = {"id": "origins-12", "name": "Emberwyrm Sovereign"}
    if pricing is not None:
        card["pricing"] = pricing
    return card


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@pytest.mark.asyncio
async def test_fetch_leads_with_cardmarket_trend() -> None:
    payload = _card_payload(
        {
            "cardmarket": {
                "trend": 757.10,
                "avg30": 529.99,
                "low": 100.0,
                "updated": _now_iso(),
                "idProduct": 273699,
            }
        }
    )
    async with _client(lambda _req: httpx.Response(200, json=payload)) as client:
        price = await client.fetch_cardmarket_price("origins-12")

    assert price.trend_eur == Decimal("757.10")
    assert price.display_value == Decimal("757.10")
    assert price.product_id == 273699
    assert price.listing_url is not None and "273699" in price.listing_url
    assert price.age_hours < 1


@pytest.mark.asyncio
async def test_display_value_falls_back_to_avg30_when_trend_missing() -> None:
    payload = _card_payload(
        {"cardmarket": {"avg30": 529.99, "updated": _now_iso()}}
    )
    async with _client(lambda _req: httpx.Response(200, json=payload)) as client:
        price = await client.fetch_cardmarket_price("origins-12")

    assert price.trend_eur is None
    assert price.display_value == Decimal("529.99")


@pytest.mark.asyncio
async def test_fetch_targets_locale_specific_path() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        return httpx.Response(
            200, json=_card_payload({"cardmarket": {"trend": 1.0, "updated": _now_iso()}})
        )

    async with _client(handler) as client:
        await client.fetch_cardmarket_price("origins-12", locale="fr")

    assert seen == ["/v2/fr/cards/origins-12"]


@pytest.mark.asyncio
async def test_missing_cardmarket_block_raises_price_unavailable() -> None:
    payload = _card_payload({"tcgplayer": {"trend": 12.0}})  # exists, no cardmarket
    async with _client(lambda _req: httpx.Response(200, json=payload)) as client:
        with pytest.raises(PriceUnavailable):
            await client.fetch_cardmarket_price("origins-12")


@pytest.mark.asyncio
async def test_unknown_card_raises_card_not_found() -> None:
    async with _client(lambda _req: httpx.Response(404)) as client:
        with pytest.raises(CardNotFound):
            await client.fetch_cardmarket_price("nope-999")


def test_to_decimal_passes_none_through_and_avoids_binary_float_noise() -> None:
    assert to_decimal(None) is None
    assert to_decimal(0.1) == Decimal("0.1")  # not Decimal(0.1000000000000000055…)


@pytest.mark.asyncio
async def test_provider_maps_trend_reading_to_quote() -> None:
    payload = _card_payload(
        {"cardmarket": {"trend": 757.10, "low": 100.0, "updated": _now_iso(),
                        "idProduct": 273699}}
    )
    async with _client(lambda _req: httpx.Response(200, json=payload)) as client:
        quote = await TcgdexPricingProvider(client).price("origins-12")

    assert quote.value == Decimal("757.10")
    assert quote.basis == "trend"
    assert quote.currency == "EUR"
    assert quote.source == "cardmarket_via_tcgdex"


@pytest.mark.asyncio
async def test_provider_translates_not_found() -> None:
    async with _client(lambda _req: httpx.Response(404)) as client:
        with pytest.raises(CardNotFoundError):
            await TcgdexPricingProvider(client).price("nope-999")


@pytest.mark.asyncio
async def test_provider_translates_price_unavailable() -> None:
    payload = _card_payload({"tcgplayer": {"trend": 1.0}})
    async with _client(lambda _req: httpx.Response(200, json=payload)) as client:
        with pytest.raises(PriceUnavailableError):
            await TcgdexPricingProvider(client).price("origins-12")


@pytest.mark.asyncio
async def test_provider_translates_transport_failure_to_upstream_error() -> None:
    def handler(_req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("boom")

    async with _client(handler) as client:
        with pytest.raises(UpstreamUnavailableError):
            await TcgdexPricingProvider(client).price("origins-12")
