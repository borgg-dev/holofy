"""Unit coverage for the disambiguation logic in variant_spread.

Network is mocked via httpx.MockTransport so the suite is hermetic. The handler routes
the two calls the tool makes — the name-filtered list and the per-card detail — from an
in-memory catalog, so the tests pin the behaviour the spike reasons about (variant
resolution, the ×N spread maths, unpriced-printing handling, exact-name routing) rather
than the live API's current numbers.
"""

from __future__ import annotations

from decimal import Decimal

import httpx
import pytest

from variant_spread import (
    CardNotFound,
    Printing,
    Spread,
    _resolve_variant,
    _to_decimal,
    enumerate_printings,
)

# Three printings of one name: a vintage holo, its budget reprint, and a card the feed
# carries no price for — the shape the disambiguator has to survive.
_CATALOG: dict[str, dict] = {
    "base1-4": {
        "id": "base1-4",
        "name": "Charizard",
        "localId": "4",
        "variants": {"firstEdition": True, "holo": True},
        "set": {"name": "Base Set", "cardCount": {"official": 102}},
        "pricing": {"cardmarket": {"trend": 757.10, "idProduct": 273699}},
    },
    "swsh4-25": {
        "id": "swsh4-25",
        "name": "Charizard",
        "localId": "25",
        "variants": {"normal": True, "reverse": True},
        "set": {"name": "Vivid Voltage", "cardCount": {"official": 185}},
        "pricing": {"cardmarket": {"trend": 2.02, "idProduct": 410001}},
    },
    "2024sv-1": {
        "id": "2024sv-1",
        "name": "Charizard",
        "localId": "1",
        "variants": {"holo": True},
        "set": {"name": "Scarlet & Violet Promos", "cardCount": {}},
        "pricing": {},
    },
}


def _handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path.endswith("/cards"):
        name = request.url.params.get("name", "")
        wanted = name.removeprefix("eq:")
        stubs = [
            {"id": c["id"], "name": c["name"]}
            for c in _CATALOG.values()
            if c["name"] == wanted
        ]
        return httpx.Response(200, json=stubs)
    card_id = path.rsplit("/", 1)[-1]
    if card_id not in _CATALOG:
        return httpx.Response(404)
    return httpx.Response(200, json=_CATALOG[card_id])


def _client() -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(_handler))


def test_enumerate_resolves_tuple_and_orders_dearest_first() -> None:
    with _client() as client:
        spread = enumerate_printings("Charizard", client=client)

    assert [p.set_name for p in spread.printings] == [
        "Base Set",
        "Vivid Voltage",
        "Scarlet & Violet Promos",  # unpriced sinks to the bottom
    ]
    base = spread.printings[0]
    assert base.set_code == "4/102"
    assert base.variant == "1st Edition"
    assert base.trend_eur == Decimal("757.10")


def test_spread_factor_is_dearest_over_cheapest_priced() -> None:
    with _client() as client:
        spread = enumerate_printings("Charizard", client=client)

    assert spread.dearest is not None and spread.cheapest is not None
    assert spread.dearest.set_name == "Base Set"
    assert spread.cheapest.set_name == "Vivid Voltage"
    # 757.10 / 2.02 ≈ 374.8
    assert spread.factor is not None
    assert round(spread.factor, 1) == Decimal("374.8")


def test_unpriced_printing_is_excluded_from_spread_maths() -> None:
    with _client() as client:
        spread = enumerate_printings("Charizard", client=client)

    assert len(spread.printings) == 3
    assert len(spread.priced) == 2
    assert all(p.trend_eur is not None for p in spread.priced)


def test_unknown_name_raises_card_not_found() -> None:
    with _client() as client:
        with pytest.raises(CardNotFound):
            enumerate_printings("Mewthree", client=client)


def test_limit_caps_detail_fetches() -> None:
    with _client() as client:
        spread = enumerate_printings("Charizard", limit=1, client=client)

    assert len(spread.printings) == 1


def test_set_code_falls_back_to_bare_number_without_total() -> None:
    promo = Printing(
        card_id="2024sv-1", name="Charizard", set_name="SV Promos",
        collector_number="1", set_total=None, variant="Holo",
        trend_eur=None, product_id=None,
    )
    assert promo.set_code == "1"


def test_factor_is_none_when_nothing_priced() -> None:
    bare = Printing(
        card_id="x", name="x", set_name="x", collector_number="1", set_total=10,
        variant="Holo", trend_eur=None, product_id=None,
    )
    assert Spread(name="x", printings=(bare,)).factor is None


@pytest.mark.parametrize(
    ("variants", "expected"),
    [
        ({"firstEdition": True, "holo": True}, "1st Edition"),
        ({"holo": True, "reverse": True}, "Holo"),
        ({"reverse": True, "normal": True}, "Reverse Holo"),
        ({"normal": True}, "Normal"),
        ({}, "Unknown"),
    ],
)
def test_variant_resolution_follows_priority(variants: dict, expected: str) -> None:
    assert _resolve_variant(variants) == expected


def test_to_decimal_avoids_binary_float_noise() -> None:
    assert _to_decimal(None) is None
    assert _to_decimal(2.02) == Decimal("2.02")
