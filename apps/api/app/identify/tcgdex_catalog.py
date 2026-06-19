"""A ``CatalogIndex`` backed by the TCGdex catalog — the whole Pokémon universe, not seeds.

Recall is a name search (TCGdex matches names loosely); each candidate brief is then resolved
to a full printing for its set, collector total, and variant. When the read carries a
collector numerator we pre-filter the briefs to that number before fetching details, so a
same-name search collapses to the handful of printings that could actually be the card —
cheap, and it keeps the same-art reprint pair (the disambiguation case) intact for the
resolver to score.

This is the live-API form of the index. Architecture §4 fronts it with the nightly catalog
sync into Postgres on the hot path; that cache drops in behind this same ``find`` with no
change to the resolver or provider.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

import httpx

from app.core.errors import UpstreamUnavailableError
from app.identify.catalog import CardRead, CatalogCard
from app.identify.collector_number import parse_collector_number
from app.providers.pricing.tcgdex import CardNotFound, TcgdexClient
from app.schemas.cards import CardIdentity, Variant

# A name search can return many printings; cap how many we resolve to full records so one
# scan can't fan out into dozens of detail fetches.
_MAX_CANDIDATES = 16


class TcgdexCatalogIndex:
    def __init__(self, client: TcgdexClient, *, locale: str = "en") -> None:
        self._client = client
        self._locale = locale

    async def find(self, read: CardRead) -> Sequence[CatalogCard]:
        if not read.name:
            # Without a name there's nothing to search the catalog on — a number alone can't
            # be located across sets. Honest empty result rather than a guess.
            return []

        try:
            briefs = await self._client.search_cards(name=read.name, locale=self._locale)
            number = parse_collector_number(read.collector_number)
            if number is not None and number.numerator is not None:
                briefs = [b for b in briefs if _brief_numerator(b) == number.numerator] or briefs

            ids = [b["id"] for b in briefs[:_MAX_CANDIDATES] if b.get("id")]
            cards = await asyncio.gather(*(self._resolve(card_id) for card_id in ids))
        except httpx.HTTPError as exc:
            # TCGdex is down/slow: a scan must degrade to a typed 502 the client can show as
            # "try again", never a raw 500. The owned OCR already ran; only the catalog failed.
            raise UpstreamUnavailableError(
                "The card catalog is temporarily unavailable. Please try again shortly.",
                details={"upstream": "tcgdex"},
            ) from exc
        return [card for card in cards if card is not None]

    async def _resolve(self, card_id: str) -> CatalogCard | None:
        try:
            card = await self._client.get_card(card_id, locale=self._locale)
        except CardNotFound:
            return None
        return _to_catalog_card(card, locale=self._locale)


def _brief_numerator(brief: dict) -> int | None:
    number = parse_collector_number(str(brief.get("localId", "")))
    return number.numerator if number else None


def _collector_number(card: dict) -> str:
    local_id = str(card.get("localId", "")).strip()
    total = ((card.get("set") or {}).get("cardCount") or {}).get("official")
    return f"{local_id}/{total}" if total else local_id


def _primary_variant(card: dict) -> Variant:
    # A TCGdex card flags every printing variant it was sold in; we pick the one that most
    # defines its identity/value, holo-first. Multi-variant splits are refined later.
    variants = card.get("variants") or {}
    if variants.get("holo"):
        return Variant.HOLO
    if variants.get("reverse"):
        return Variant.REVERSE_HOLO
    if variants.get("firstEdition"):
        return Variant.FIRST_EDITION
    return Variant.NORMAL


def _to_catalog_card(card: dict, *, locale: str) -> CatalogCard | None:
    number_str = _collector_number(card)
    number = parse_collector_number(number_str)
    if number is None:
        return None
    return CatalogCard(
        identity=CardIdentity(
            canonical_id=card["id"],
            name=card["name"],
            set_name=(card.get("set") or {}).get("name", ""),
            collector_number=number_str,
            language=locale,
            variant=_primary_variant(card),
        ),
        number=number,
    )
