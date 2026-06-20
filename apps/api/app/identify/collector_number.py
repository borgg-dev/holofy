"""Collector numbers — the field that separates same-art Pokémon reprints.

A printing's collector number ("12/120": the 12th card in a 120-card set) is the single
strongest cheap signal for identity: two sets can share a card's name and artwork but never
the same ``number/total`` (ADR 0002). Phone OCR routinely reads the numerator but drops or
garbles the set total, so the parse keeps them separate and the match degrades gracefully —
a numerator-only read is a *partial* match (it narrows, it doesn't pin), which is exactly
what should route to a confirm rather than a silent commit.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import IntEnum

# A collector number is a standalone numeric token: "12/120" (numerator/total) or a bare
# "12". An alphanumeric promo code ("SWSH039") is deliberately *not* split into a numerator —
# its digits aren't a set position, so it keeps its raw form and matches on the raw string.
_FULL_NUMBER = re.compile(r"^(\d+)\s*/\s*(\d+)$")
_NUMERATOR_ONLY = re.compile(r"^(\d+)$")
# An "n/total" embedded anywhere in a noisier token — older cards print the collector number
# inside a dense copyright line (e.g. "…1999 Wizards. 58/102") rather than as its own token, so
# the strict anchored parse misses it. Bounded to ≤4 digits so it can't latch onto a long ID.
_EMBEDDED_FULL = re.compile(r"(\d{1,4})\s*/\s*(\d{1,4})")


@dataclass(frozen=True, slots=True)
class CollectorNumber:
    raw: str
    numerator: int | None
    denominator: int | None


class NumberMatch(IntEnum):
    """How strongly a read collector number pins a catalog entry. Ordered so ``max`` works."""

    NONE = 0
    PARTIAL = 1  # numerator agrees but the set total is unknown/unmatched — narrows only
    EXACT = 2  # numerator and set total both agree — pins a single printing


def parse_collector_number(raw: str | None) -> CollectorNumber | None:
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None
    if (full := _FULL_NUMBER.match(text)) is not None:
        return CollectorNumber(raw=text, numerator=int(full.group(1)), denominator=int(full.group(2)))
    if (numerator := _NUMERATOR_ONLY.match(text)) is not None:
        return CollectorNumber(raw=text, numerator=int(numerator.group(1)), denominator=None)
    # A non-numeric number (e.g. a promo code) still identifies via its raw string.
    return CollectorNumber(raw=text, numerator=None, denominator=None)


def search_collector_number(text: str | None) -> CollectorNumber | None:
    """Find the collector number *within* an OCR token, not just when the token is exactly one.

    An "n/total" embedded anywhere wins (it's unambiguous even buried in a copyright line); a
    token that is *itself* a bare number is taken as a numerator-only read. A bare number must
    be the whole token — we never carve a digit out of a word — so this stays as precise as the
    strict parse while rescuing the embedded-number case. Returns the cleaned "n/total" form so
    everything downstream matches on the canonical number, not the noisy surrounding text.
    """
    if text is None:
        return None
    if (m := _EMBEDDED_FULL.search(text)) is not None:
        num, total = int(m.group(1)), int(m.group(2))
        return CollectorNumber(raw=f"{num}/{total}", numerator=num, denominator=total)
    stripped = text.strip()
    if (m := _NUMERATOR_ONLY.match(stripped)) is not None:
        return CollectorNumber(raw=stripped, numerator=int(m.group(1)), denominator=None)
    return None


def match_strength(read: CollectorNumber | None, entry: CollectorNumber | None) -> NumberMatch:
    """Compare a read number against a catalog entry's number."""
    if read is None or entry is None:
        return NumberMatch.NONE
    if read.numerator is not None and entry.numerator is not None:
        if read.numerator != entry.numerator:
            return NumberMatch.NONE
        # Numerator agrees; the set total promotes it to an exact pin when both are known.
        if read.denominator is not None and entry.denominator is not None:
            return NumberMatch.EXACT if read.denominator == entry.denominator else NumberMatch.NONE
        return NumberMatch.PARTIAL
    # Neither carries a numerator — fall back to a raw-string equality (promo codes).
    if read.numerator is None and entry.numerator is None:
        return NumberMatch.EXACT if read.raw.lower() == entry.raw.lower() else NumberMatch.NONE
    return NumberMatch.NONE
