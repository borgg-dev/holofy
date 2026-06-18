"""Reference-catalog implementation of the existence cross-check (the mock for now).

The real check queries the nightly-synced reference DB (architecture §4); until that sync
exists, this answers from a small, explicit reference of known printings. It is built to
catch the case the cross-check exists for: a tuple whose *base card* (set + collector number)
is genuine but whose **variant was never issued** for that card — e.g. a holo of a card only
ever printed as a common. That is the strongest single fake contributor, and it is exactly
what artwork matching alone misses.

Resolution logic, deliberately conservative:

- The base card (set + number, in a known language) is **unknown** → ``unverifiable``. We
  don't claim a printing never existed just because our reference is incomplete; an absent
  reference is our gap, not the card's fault (so it must never read as a fake signal).
- The base card is known and the requested variant **is** among its issued variants →
  ``confirmed``.
- The base card is known and the requested variant is **not** among its issued variants →
  ``not_in_catalog``: a variant of a real card that was never printed in that form.
- The language is outside our reference's coverage → ``unverifiable`` (same reasoning).
"""

from __future__ import annotations

from app.authenticity.catalog_existence import CatalogExistence, CardTuple

# (set_code, collector_number) → the variants actually issued for that printing, by language.
# Holofy's own invented catalog (no real trademarks): the Emberwyrm/Tidecaller cards the
# recognition mock resolves to. The load-bearing fixture is ``origins-12``: issued as a holo
# but never as a 1st-edition, so a 1st-edition Emberwyrm is a never-printed variant the
# cross-check must flag.
_KNOWN_PRINTINGS: dict[tuple[str, str], dict[str, frozenset[str]]] = {
    ("origins", "12/120"): {"en": frozenset({"holo", "reverse_holo"})},
    ("origins", "8/120"): {"en": frozenset({"holo", "normal"})},
    ("echo", "12/95"): {"en": frozenset({"holo", "normal"})},
}


class ReferenceCatalogExistenceChecker:
    """Resolves a card tuple against a fixed reference of known printings.

    Stateless and deterministic; the real reference-DB-backed checker drops in behind the
    same ``CatalogExistenceChecker`` Protocol once the nightly sync lands.
    """

    async def check(self, card: CardTuple) -> CatalogExistence:
        issued_by_language = _KNOWN_PRINTINGS.get((card.set_code, card.collector_number))
        if issued_by_language is None:
            # We have no reference for this base card — can't claim it was never printed.
            return CatalogExistence.UNVERIFIABLE

        issued_variants = issued_by_language.get(card.language)
        if issued_variants is None:
            # Known card, but our reference has no coverage for this language/region.
            return CatalogExistence.UNVERIFIABLE

        if card.variant in issued_variants:
            return CatalogExistence.CONFIRMED
        return CatalogExistence.NOT_IN_CATALOG
