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


@pytest.mark.asyncio
async def test_accented_name_misses_direct_search_but_recovers_via_name_index() -> None:
    # The reported bug: OCR reads "Salameche" (no accent); TCGdex's accent-sensitive name search
    # returns nothing, so without the de-accented name index the scan finds zero candidates.
    from app.identify.catalog_name_index import CatalogNameIndex

    full = [
        {"id": "det1-4", "localId": "4", "name": "Salamèche"},
        {"id": "sm7.5-1", "localId": "1", "name": "Salamèche"},
    ]
    card = {
        "id": "det1-4",
        "name": "Salamèche",
        "localId": "4",
        "set": {"name": "Détective Pikachu", "cardCount": {"official": 18}},
        "variants": {"normal": True},
    }

    def _handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/cards"):
            # Accent-sensitive: the de-accented "Salameche" query matches nothing; the unfiltered
            # bulk list (no name param) returns the real accented briefs.
            if "name" in request.url.params:
                return httpx.Response(200, json=[])
            return httpx.Response(200, json=full)
        if path.rsplit("/", 1)[-1] == "det1-4":
            return httpx.Response(200, json=card)
        return httpx.Response(404)

    client = TcgdexClient(client=httpx.AsyncClient(transport=httpx.MockTransport(_handler)))
    index = TcgdexCatalogIndex(
        client, locales=["fr"], name_index=CatalogNameIndex(client, locales=["fr"])
    )
    cards = await index.find(CardRead(name="Salameche", collector_number="4/18"))
    assert [c.identity.canonical_id for c in cards] == ["det1-4"]
    await client.aclose()


@pytest.mark.asyncio
async def test_catalog_outage_raises_typed_upstream_error_not_500() -> None:
    # When TCGdex is unreachable, find() must raise the typed UpstreamUnavailableError (→ 502),
    # so a scan degrades to "try again", never a raw 500.
    from app.core.errors import UpstreamUnavailableError

    def _down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("tcgdex unreachable", request=request)

    client = TcgdexClient(client=httpx.AsyncClient(transport=httpx.MockTransport(_down)))
    index = TcgdexCatalogIndex(client, locales=["en"])
    with pytest.raises(UpstreamUnavailableError):
        await index.find(CardRead(name="Pikachu", collector_number="58/102"))
    await client.aclose()
