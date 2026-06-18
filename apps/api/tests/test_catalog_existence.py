"""Coverage for the catalog-existence cross-check — the never-printed-variant detector.

The cross-check is the strongest single fake contributor (architecture §3.3): a variant a
real card was never issued in. These tests pin the three outcomes — confirmed, the
never-printed variant, and the deliberately-conservative ``unverifiable`` (our reference
gap, which must never read as a fake signal).
"""

from __future__ import annotations

import pytest

from app.authenticity.catalog_existence import CatalogExistence, CardTuple
from app.authenticity.reference_catalog import ReferenceCatalogExistenceChecker


def _checker() -> ReferenceCatalogExistenceChecker:
    return ReferenceCatalogExistenceChecker()


@pytest.mark.asyncio
async def test_a_known_printing_in_an_issued_variant_is_confirmed() -> None:
    result = await _checker().check(
        CardTuple(set_code="origins", collector_number="12/120", variant="holo", language="en")
    )
    assert result is CatalogExistence.CONFIRMED


@pytest.mark.asyncio
async def test_a_never_printed_variant_of_a_real_card_is_flagged() -> None:
    # origins-12 was issued as a holo but never as a 1st-edition: the cross-check must catch
    # the variant that was never printed — the case artwork matching alone misses.
    result = await _checker().check(
        CardTuple(
            set_code="origins",
            collector_number="12/120",
            variant="first_edition",
            language="en",
        )
    )
    assert result is CatalogExistence.NOT_IN_CATALOG


@pytest.mark.asyncio
async def test_an_unknown_base_card_is_unverifiable_not_a_fake_signal() -> None:
    # We have no reference for this card — we must not claim it was never printed. An absent
    # reference is our gap, not a finding about the card (charter §3.1 honest framing).
    result = await _checker().check(
        CardTuple(set_code="unknown", collector_number="999/999", variant="holo", language="en")
    )
    assert result is CatalogExistence.UNVERIFIABLE


@pytest.mark.asyncio
async def test_a_language_outside_coverage_is_unverifiable() -> None:
    result = await _checker().check(
        CardTuple(set_code="origins", collector_number="12/120", variant="holo", language="jp")
    )
    assert result is CatalogExistence.UNVERIFIABLE
