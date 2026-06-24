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
from app.identify.catalog_name_index import CatalogNameIndex
from app.identify.collector_number import parse_collector_number
from app.providers.pricing.tcgdex import CardNotFound, TcgdexClient
from app.schemas.cards import CardIdentity, Variant

# A name search can return many printings; cap how many we resolve to full records so one
# scan can't fan out into dozens of detail fetches.
_MAX_CANDIDATES = 16


class TcgdexCatalogIndex:
    """Resolve an OCR'd name+number against TCGdex across one or more language catalogs.

    A card is printed in its own language — a French Charizard reads "Dracaufeu", a German one
    "Glurak" — so the OCR'd name only matches the catalog *in that card's locale*. We search
    every configured locale and union the hits: the card's own language returns it, the others
    return nothing, so a French card resolves without us having to know up front which language
    it is. Each hit is resolved in the locale it was found in, so its catalog name comes back in
    the same language the OCR read — which is what lets the resolver corroborate the name.
    """

    def __init__(
        self,
        client: TcgdexClient,
        *,
        locales: Sequence[str] = ("en",),
        name_index: "CatalogNameIndex | None" = None,
    ) -> None:
        self._client = client
        self._locales = tuple(locales) or ("en",)
        # Accent-insensitive recall: consulted only when the direct (accent-sensitive) search
        # returns nothing, so a diacritic the OCR dropped doesn't silently lose the card.
        self._name_index = name_index

    async def find(self, read: CardRead) -> Sequence[CatalogCard]:
        if not read.name:
            # Without a name there's nothing to search the catalog on — a number alone can't
            # be located across sets. Honest empty result rather than a guess.
            return []

        number = parse_collector_number(read.collector_number)
        per_locale = await asyncio.gather(
            *(self._find_in_locale(read.name, number, locale) for locale in self._locales),
            return_exceptions=True,
        )

        # Only fail the scan if *every* locale's catalog call failed — a single language being
        # down must not blind the others.
        errors = [r for r in per_locale if isinstance(r, BaseException)]
        if errors and len(errors) == len(per_locale):
            raise UpstreamUnavailableError(
                "The card catalog is temporarily unavailable. Please try again shortly.",
                details={"upstream": "tcgdex"},
            ) from errors[0]

        seen: set[str] = set()
        merged: list[CatalogCard] = []
        for result in per_locale:
            if isinstance(result, BaseException):
                continue
            for card in result:
                if card.identity.canonical_id in seen:
                    continue
                seen.add(card.identity.canonical_id)
                merged.append(card)
        return merged

    async def _find_in_locale(
        self, name: str, number, locale: str
    ) -> list[CatalogCard]:
        try:
            briefs = await self._client.search_cards(name=name, locale=locale)
            if number is not None and number.numerator is not None:
                briefs = [b for b in briefs if _brief_numerator(b) == number.numerator] or briefs
            ids = [b["id"] for b in briefs[:_MAX_CANDIDATES] if b.get("id")]
            # Direct search found nothing — the name likely carries a diacritic the OCR dropped
            # (TCGdex's name filter is accent-sensitive). Recover via the de-accented name index.
            if not ids and self._name_index is not None:
                numerator = number.numerator if number is not None else None
                ids = (await self._name_index.lookup(name, locale, numerator=numerator))[
                    :_MAX_CANDIDATES
                ]
            cards = await asyncio.gather(*(self._resolve(card_id, locale) for card_id in ids))
        except httpx.HTTPError as exc:
            # Surface as the typed upstream error; find() decides whether any locale survived.
            raise UpstreamUnavailableError(
                "The card catalog is temporarily unavailable. Please try again shortly.",
                details={"upstream": "tcgdex", "locale": locale},
            ) from exc
        return [card for card in cards if card is not None]

    async def _resolve(self, card_id: str, locale: str) -> CatalogCard | None:
        try:
            card = await self._client.get_card(card_id, locale=locale)
        except CardNotFound:
            return None
        return _to_catalog_card(card, locale=locale)


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
            image_url=_image_url(card),
        ),
        number=number,
    )


def _image_url(card: dict) -> str | None:
    """The full artwork URL for the card's real face.

    TCGdex returns ``image`` as a base path without quality/extension (e.g.
    ``…/base/base1/58``); the client renders the card face from it, so we resolve it to a
    concrete high-res WebP (``…/58/high.webp``). Absent for some printings — return ``None``
    so the client falls back to the placeholder rather than a broken image.
    """
    base = card.get("image")
    if not base:
        return None
    return f"{base}/high.webp"
