"""Unit coverage for the branching logic in tcgdex_prices.

Network is mocked via httpx.MockTransport so the suite is hermetic — these tests
pin the behaviour the spike actually reasons about (staleness boundary, the
trend→avg30 fallback, null-price degradation, and the two not-found paths), not
the live API's current numbers.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import httpx
import pytest

from tcgdex_prices import (
    CardmarketPrice,
    CardNotFound,
    PriceUnavailable,
    _to_decimal,
    fetch_cardmarket_price,
)


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _card_payload(pricing: dict | None) -> dict:
    card: dict = {"id": "base1-4", "name": "Charizard"}
    if pricing is not None:
        card["pricing"] = pricing
    return card


def test_fetch_leads_with_cardmarket_trend() -> None:
    updated = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    payload = _card_payload(
        {"cardmarket": {"trend": 757.10, "avg30": 529.99, "low": 100.0,
                        "updated": updated, "idProduct": 273699}}
    )
    with _client(lambda _req: httpx.Response(200, json=payload)) as client:
        price = fetch_cardmarket_price("base1-4", client=client)

    assert price.trend_eur == Decimal("757.10")
    assert price.display_value == Decimal("757.10")
    assert price.product_id == 273699


def test_display_value_falls_back_to_avg30_when_trend_missing() -> None:
    price = CardmarketPrice(
        card_id="base1-4", card_name="Charizard",
        trend_eur=None, avg30_eur=Decimal("529.99"), low_eur=None,
        updated=datetime.now(timezone.utc), product_id=None, locale="en",
    )
    assert price.display_value == Decimal("529.99")


@pytest.mark.parametrize(
    ("age", "expected"),
    [(timedelta(hours=10), "10h old"), (timedelta(hours=35), "35h old"),
     (timedelta(hours=36), "1d old"), (timedelta(days=3), "3d old")],
)
def test_staleness_switches_to_days_at_36h(age: timedelta, expected: str) -> None:
    price = CardmarketPrice(
        card_id="x", card_name="x", trend_eur=None, avg30_eur=None, low_eur=None,
        updated=datetime.now(timezone.utc) - age, product_id=None, locale="en",
    )
    assert price.staleness == expected


def test_missing_cardmarket_block_raises_price_unavailable() -> None:
    payload = _card_payload({"tcgplayer": {"trend": 12.0}})  # exists, but no cardmarket
    with _client(lambda _req: httpx.Response(200, json=payload)) as client:
        with pytest.raises(PriceUnavailable):
            fetch_cardmarket_price("base1-4", client=client)


def test_unknown_card_raises_card_not_found() -> None:
    with _client(lambda _req: httpx.Response(404)) as client:
        with pytest.raises(CardNotFound):
            fetch_cardmarket_price("nope-999", client=client)


def test_to_decimal_passes_none_through_and_avoids_binary_float_noise() -> None:
    assert _to_decimal(None) is None
    assert _to_decimal(0.1) == Decimal("0.1")  # not Decimal(0.1000000000000000055…)
