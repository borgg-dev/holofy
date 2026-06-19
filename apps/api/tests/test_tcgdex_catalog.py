"""The TCGdex-backed catalog index — hermetic via httpx.MockTransport (the spike pattern).

Pins the behaviour identity depends on: a name search recalls candidates, a known collector
numerator pre-filters them before the detail fetches, and each brief resolves to a CatalogCard
with set name, collector total, and variant — leaving the same-art reprint pair intact for the
resolver to disambiguate.
"""

from __future__ import annotations

import httpx
import pytest

from app.identify.catalog import CardRead
from app.identify.resolver import CardResolver
from app.identify.tcgdex_catalog import TcgdexCatalogIndex
from app.providers.pricing.tcgdex import TcgdexClient

_BRIEFS = [
    {"id": "origins-12", "localId": "12", "name": "Emberwyrm Sovereign"},
    {"id": "echo-12", "localId": "12", "name": "Emberwyrm Sovereign"},
    {"id": "promo-99", "localId": "99", "name": "Emberwyrm Sovereign Promo"},
]
_CARDS = {
    "origins-12": {
        "id": "origins-12",
        "name": "Emberwyrm Sovereign",
        "localId": "12",
        "set": {"name": "Origins Vault", "cardCount": {"official": 120}},
        "variants": {"holo": True},
    },
    "echo-12": {
        "id": "echo-12",
        "name": "Emberwyrm Sovereign",
        "localId": "12",
        "set": {"name": "Echo Reprint", "cardCount": {"official": 95}},
        "variants": {"holo": True},
    },
}


def _handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path.endswith("/cards"):
        return httpx.Response(200, json=_BRIEFS)
    card_id = path.rsplit("/", 1)[-1]
    if card_id in _CARDS:
        return httpx.Response(200, json=_CARDS[card_id])
    return httpx.Response(404)


def _index() -> TcgdexCatalogIndex:
    client = TcgdexClient(client=httpx.AsyncClient(transport=httpx.MockTransport(_handler)))
    return TcgdexCatalogIndex(client)


@pytest.mark.asyncio
async def test_find_resolves_briefs_to_full_printings_and_pre_filters_by_number() -> None:
    index = _index()
    cards = await index.find(CardRead(collector_number="12/120", name="Emberwyrm Sovereign"))

    by_id = {c.identity.canonical_id: c for c in cards}
    # The promo (localId 99) is pre-filtered out by the read's numerator (12); the two
    # same-name "12" printings remain, resolved to their sets + totals.
    assert set(by_id) == {"origins-12", "echo-12"}
    assert by_id["origins-12"].identity.collector_number == "12/120"
    assert by_id["echo-12"].identity.collector_number == "12/95"
    assert by_id["origins-12"].identity.set_name == "Origins Vault"


@pytest.mark.asyncio
async def test_find_feeds_the_resolver_to_pin_the_right_reprint() -> None:
    result = await CardResolver(_index()).resolve(
        CardRead(collector_number="12/120", name="Emberwyrm Sovereign", quality=0.95)
    )
    assert result.candidates[0].identity.canonical_id == "origins-12"


@pytest.mark.asyncio
async def test_find_without_a_name_returns_nothing() -> None:
    cards = await _index().find(CardRead(collector_number="12/120"))
    assert cards == []
