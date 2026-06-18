"""The catalog-existence cross-check — the strongest single fake signal (architecture §3.3).

A counterfeit frequently exists in a combination that *was never printed*: a holo of a card
only ever issued as a common, a 1st-edition stamp on a set that never had one, an English
print of a Japan-only promo. Artwork matching can't catch this — only checking the resolved
``(set, collector number, variant, language/era)`` tuple against the real reference catalog
can. So this is a deterministic lookup the service owns, not a learned model output.

This module is the *seam* for that lookup, mirroring ``app.grading.capture_store``: the
real implementation queries the nightly-synced reference DB; the mock answers from a small
fixed set of known printings so the whole flow — and the "never-printed variant" test — runs
with no catalog sync and no network.

The result is deliberately tri-state, not a boolean: a tuple can be *confirmed* printed,
*not* in the catalog (a strong risk contributor), or *unverifiable* because the reference
catalog has no coverage for that region/era yet (which must widen uncertainty, never count
as a fake signal — an absent reference is our gap, not the card's fault).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class CatalogExistence(StrEnum):
    """Whether the resolved card tuple corresponds to a printing that actually exists.

    ``confirmed`` — the tuple matches a known printing. ``not_in_catalog`` — no printing
    matches it (a strong fake contributor: a never-issued variant). ``unverifiable`` — the
    reference catalog has no coverage to decide (our gap; widens uncertainty, never accuses).
    """

    CONFIRMED = "confirmed"
    NOT_IN_CATALOG = "not_in_catalog"
    UNVERIFIABLE = "unverifiable"


@dataclass(frozen=True, slots=True)
class CardTuple:
    """The disambiguation tuple the cross-check resolves against the reference catalog."""

    set_code: str
    collector_number: str
    variant: str
    language: str


class CatalogExistenceChecker(Protocol):
    async def check(self, card: CardTuple) -> CatalogExistence:
        """Resolve whether ``card`` corresponds to a printing the reference catalog knows."""
        ...
