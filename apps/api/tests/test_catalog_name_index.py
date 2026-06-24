"""The accent-insensitive catalog name index — the recovery for diacritic-blind OCR.

TCGdex's name search is accent-*sensitive*, so an OCR read that drops a diacritic ("Salameche")
misses the catalog name ("Salamèche") and the scan finds nothing. These pin the recovery: the
full brief list is pulled once, de-accented, and matched locally; the bulk fetch is cached and
warmed; a failed fetch degrades to an honest empty result, never an error.
"""

from __future__ import annotations

import httpx
import pytest

from app.identify.catalog_name_index import CatalogNameIndex, deaccent
from app.providers.pricing.tcgdex import TcgdexClient

# Two accented printings of Salamèche (French Charmander) at different collector numbers, plus an
# unrelated accented name that must not be recalled for a "salameche" read.
_BRIEFS = [
    {"id": "sm7.5-1", "localId": "1", "name": "Salamèche"},
    {"id": "det1-4", "localId": "4", "name": "Salamèche"},
    {"id": "xy1-1", "localId": "1", "name": "Florizarre"},
    {"id": "evo-1", "localId": "1", "name": "Évoli"},
]


def _client(handler) -> TcgdexClient:
    return TcgdexClient(client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))


def _ok(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json=_BRIEFS)


def test_deaccent_folds_diacritics_and_case() -> None:
    assert deaccent("Salamèche") == "salameche"
    assert deaccent("Évoli") == "evoli"  # leading accent — where prefix tricks fail
    assert deaccent("Dracaufeu") == "dracaufeu"


@pytest.mark.asyncio
async def test_lookup_recovers_accented_name_from_deaccented_read() -> None:
    index = CatalogNameIndex(_client(_ok), locales=["fr"])
    ids = await index.lookup("Salameche", "fr")
    assert set(ids) == {"sm7.5-1", "det1-4"}


@pytest.mark.asyncio
async def test_lookup_handles_leading_accent() -> None:
    index = CatalogNameIndex(_client(_ok), locales=["fr"])
    assert await index.lookup("Evoli", "fr") == ["evo-1"]


@pytest.mark.asyncio
async def test_lookup_pins_to_collector_numerator_when_given() -> None:
    index = CatalogNameIndex(_client(_ok), locales=["fr"])
    assert await index.lookup("Salameche", "fr", numerator=4) == ["det1-4"]


@pytest.mark.asyncio
async def test_numerator_pin_falls_back_to_name_hits_when_no_number_matches() -> None:
    # A misread number must not erase a confident name match — recall over precision.
    index = CatalogNameIndex(_client(_ok), locales=["fr"])
    assert set(await index.lookup("Salameche", "fr", numerator=999)) == {"sm7.5-1", "det1-4"}


@pytest.mark.asyncio
async def test_unrelated_name_is_not_recalled() -> None:
    index = CatalogNameIndex(_client(_ok), locales=["fr"])
    assert await index.lookup("Pikachu", "fr") == []


@pytest.mark.asyncio
async def test_bulk_list_is_fetched_once_and_cached() -> None:
    calls = {"n": 0}

    def _counting(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json=_BRIEFS)

    index = CatalogNameIndex(_client(_counting), locales=["fr"])
    await index.lookup("Salameche", "fr")
    await index.lookup("Florizarre", "fr")
    assert calls["n"] == 1  # second lookup served from cache


@pytest.mark.asyncio
async def test_fetch_failure_degrades_to_empty_not_error() -> None:
    def _down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("tcgdex unreachable", request=request)

    index = CatalogNameIndex(_client(_down), locales=["fr"])
    assert await index.lookup("Salameche", "fr") == []


@pytest.mark.asyncio
async def test_warm_prefetches_each_locale() -> None:
    calls: list[str] = []

    def _record(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(200, json=_BRIEFS)

    index = CatalogNameIndex(_client(_record), locales=["en", "fr"])
    await index.warm()
    # One bulk fetch per locale; a later lookup adds none.
    assert sorted(calls) == ["/v2/en/cards", "/v2/fr/cards"]
    await index.lookup("Salameche", "fr")
    assert len(calls) == 2
