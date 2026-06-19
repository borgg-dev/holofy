"""The card catalog the resolver matches reads against — our owned identity source.

A ``CardRead`` is what the *visual* stage produces from a capture (the collector number it
OCR'd, the name it read, a set hint from the symbol classifier, plus how cleanly it could
read at all). The ``CatalogIndex`` turns the read's loose signals into the small set of real
printings they could plausibly be; the resolver then scores and ranks them.

``CatalogIndex`` is a Protocol so the dev/test ``InMemoryCatalogIndex`` (a handful of our
invented cards, no network) and the production index (the nightly TCGdex catalog synced into
Postgres, per architecture §4) are interchangeable behind one ``find`` call.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol

from app.identify.collector_number import CollectorNumber, parse_collector_number
from app.schemas.cards import CardIdentity, Variant


@dataclass(frozen=True, slots=True)
class CardRead:
    """The visual stage's reading of one capture — every field is best-effort and optional.

    ``quality`` is how cleanly the card could be read (focus, glare, crop), 0–1. It is the
    ceiling on the resolver's confidence: a perfect catalog match on a smeared photo is still
    a low-confidence identification, because the inputs were weak.
    """

    collector_number: str | None = None
    name: str | None = None
    set_hint: str | None = None
    variant_hint: Variant | None = None
    quality: float = 1.0


@dataclass(frozen=True, slots=True)
class CatalogCard:
    """A catalog printing: the resolved identity plus the parsed number used to match it."""

    identity: CardIdentity
    number: CollectorNumber

    @property
    def normalized_name(self) -> str:
        return _normalize_name(self.identity.name)


class CatalogIndex(Protocol):
    async def find(self, read: CardRead) -> Sequence[CatalogCard]:
        """Recall every printing the read could plausibly be — favouring recall over
        precision, since the resolver does the precise scoring and ranking downstream.
        """
        ...


def _normalize_name(name: str) -> str:
    # Case- and whitespace-insensitive; the OCR'd name and the catalog name need only agree
    # loosely (the collector number does the precise pinning), so this stays deliberately simple.
    return " ".join(name.lower().split())


@dataclass
class InMemoryCatalogIndex:
    """A deterministic catalog over a fixed card set — dev/test stand-in for the TCGdex sync.

    Seeded with Holofy's own invented cards (no real IP), including the load-bearing
    same-art reprint pair: one creature, one artwork, two printings whose only separator is
    the collector number + set — the case identification must never silently guess (ADR 0002).
    """

    cards: list[CatalogCard] = field(default_factory=lambda: list(_DEFAULT_CARDS))

    async def find(self, read: CardRead) -> Sequence[CatalogCard]:
        number = parse_collector_number(read.collector_number)
        name = _normalize_name(read.name) if read.name else None
        hits = [
            card
            for card in self.cards
            if _recalls(card, number_numerator=number.numerator if number else None, name=name)
        ]
        # With nothing to match on, the read is too weak to narrow the catalog at all — return
        # nothing rather than the whole table, so an empty read is an honest "unrecognized".
        return hits


def _recalls(card: CatalogCard, *, number_numerator: int | None, name: str | None) -> bool:
    if number_numerator is not None and card.number.numerator == number_numerator:
        return True
    if name is not None and card.normalized_name == name:
        return True
    return False


def _entry(canonical_id: str, name: str, set_name: str, number: str) -> CatalogCard:
    parsed = parse_collector_number(number)
    assert parsed is not None  # the seeds are well-formed by construction
    return CatalogCard(
        identity=CardIdentity(
            canonical_id=canonical_id,
            name=name,
            set_name=set_name,
            collector_number=number,
            language="en",
            variant=Variant.HOLO,
        ),
        number=parsed,
    )


# The Emberwyrm pair is the disambiguation case: same name + art, two printings ~31× apart in
# price, separable only by number+set. Tidecaller is a distinct confident single.
_DEFAULT_CARDS: tuple[CatalogCard, ...] = (
    _entry("origins-8", "Tidecaller Leviath", "Origins Vault", "8/120"),
    _entry("origins-12", "Emberwyrm Sovereign", "Origins Vault", "12/120"),
    _entry("echo-12", "Emberwyrm Sovereign", "Echo Reprint", "12/95"),
)
