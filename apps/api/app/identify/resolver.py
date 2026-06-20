"""Turns a visual ``CardRead`` into a ranked, confidence-scored ``RecognitionResult``.

This is the owned core of identification — the back half of Spike B, productionized. The
scoring encodes the product's central guard (ADR 0002): the collector number, when fully
read, *pins* a single printing; a numerator-only read merely *narrows*, so two same-name
reprints stay close in score and route to the user's confirm rather than a silent commit of
a high-value variant. Read quality caps every score — a perfect catalog match on a poor
photo is still a low-confidence identification, because the inputs were weak.
"""

from __future__ import annotations

from app.identify.catalog import CardRead, CatalogCard, CatalogIndex, _normalize_name
from app.identify.collector_number import NumberMatch, match_strength, parse_collector_number
from app.schemas.cards import RecognitionCandidate, RecognitionResult

# Base score by how well the collector number matched — the dominant signal. EXACT (number +
# set total) pins; PARTIAL (numerator only) narrows; NONE leans on the weaker name/set cues.
_NUMBER_BASE: dict[NumberMatch, float] = {
    NumberMatch.EXACT: 0.90,
    NumberMatch.PARTIAL: 0.55,
    NumberMatch.NONE: 0.20,
}
_NAME_BONUS = 0.08
# A name that matches the catalog but with *no* collector number read is the common real-world
# case (a readable card whose tiny corner number didn't OCR). It is a genuine recognition — the
# card exists — so it must clear the recognition floor and route to the user's confirm step,
# never be discarded as "not a Pokémon card". This base lands it above the floor yet well below
# the commit threshold, so same-name printings still go to confirmation rather than a silent
# guess (ADR 0002): the number, when present, is what *pins* a single printing.
_NAME_ONLY_BASE = 0.50
_SET_BONUS = 0.05
_VARIANT_BONUS = 0.02
# Even a flawless match stays shy of 1.0 — recognition is never certain, and the headline
# UI should never imply it is.
_MAX_RAW = 0.98


def _name_matches(read_name: str | None, card_name: str) -> bool:
    """Whether the OCR'd name corroborates this catalog printing.

    Token-containment, not strict equality: the OCR reliably reads a card's *core* name but
    often drops a suffix the print sets smaller ("ex", "V", "GX") or a prefix ("Dark ", "M "),
    so "charizard" must still corroborate "Charizard ex". One side's words being a subset of
    the other's matches that without letting an unrelated name slip through.
    """
    if not read_name:
        return False
    r = set(read_name.split())
    c = set(card_name.split())
    if not r or not c:
        return False
    return r <= c or c <= r


class CardResolver:
    def __init__(self, catalog: CatalogIndex) -> None:
        self._catalog = catalog

    async def resolve(self, read: CardRead) -> RecognitionResult:
        cards = await self._catalog.find(read)
        read_number = parse_collector_number(read.collector_number)
        read_name = _normalize_name(read.name) if read.name else None

        candidates = [
            RecognitionCandidate(
                identity=card.identity,
                confidence=round(min(1.0, self._raw_score(card, read, read_number, read_name) * read.quality), 4),
            )
            for card in cards
        ]
        candidates.sort(key=lambda c: c.confidence, reverse=True)
        return RecognitionResult(candidates=candidates)

    def _raw_score(self, card: CatalogCard, read: CardRead, read_number, read_name) -> float:
        number_match = match_strength(read_number, card.number)
        name_match = _name_matches(read_name, card.normalized_name)
        score = _NUMBER_BASE[number_match]
        if name_match:
            # A name match with no usable number is recognition in its own right — float it to
            # the name-only base instead of merely nudging the near-floor NONE score.
            score = max(score + _NAME_BONUS, _NAME_ONLY_BASE) if number_match is NumberMatch.NONE else score + _NAME_BONUS
        if read.set_hint and read.set_hint.lower() in card.identity.set_name.lower():
            score += _SET_BONUS
        if read.variant_hint is not None and read.variant_hint == card.identity.variant:
            score += _VARIANT_BONUS
        return min(_MAX_RAW, score)
