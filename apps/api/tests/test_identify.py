"""The owned identification core: collector-number parsing/matching and the resolver that
ranks catalog candidates by read quality + match strength. Covers the confident single, the
same-art reprint that must route to a confirm, the full-number pin, and the no-match and
poor-capture paths — all deterministic, no models or network.
"""

from __future__ import annotations

import pytest

from app.identify.catalog import CardRead, InMemoryCatalogIndex
from app.identify.collector_number import NumberMatch, match_strength, parse_collector_number
from app.identify.resolver import CardResolver

_CONFIRM_THRESHOLD = 0.85


def test_parse_collector_number_forms() -> None:
    full = parse_collector_number("12/120")
    assert (full.numerator, full.denominator) == (12, 120)
    # Leading zeros and stray surrounding glyphs the OCR catches are tolerated.
    padded = parse_collector_number(" 012/120 ")
    assert (padded.numerator, padded.denominator) == (12, 120)
    numerator_only = parse_collector_number("12")
    assert (numerator_only.numerator, numerator_only.denominator) == (12, None)
    assert parse_collector_number("") is None
    # A non-numeric promo code keeps its raw form, no numerator.
    promo = parse_collector_number("SWSH039")
    assert promo.numerator is None and promo.raw == "SWSH039"


def test_match_strength_pins_only_on_full_number() -> None:
    n_12_120 = parse_collector_number("12/120")
    assert match_strength(n_12_120, parse_collector_number("12/120")) is NumberMatch.EXACT
    # Numerator agrees but the set total differs → not this printing at all.
    assert match_strength(n_12_120, parse_collector_number("12/95")) is NumberMatch.NONE
    # Numerator-only read agrees → narrows, doesn't pin.
    assert match_strength(parse_collector_number("12"), parse_collector_number("12/120")) is NumberMatch.PARTIAL
    assert match_strength(parse_collector_number("8"), parse_collector_number("12/120")) is NumberMatch.NONE


@pytest.fixture
def resolver() -> CardResolver:
    return CardResolver(InMemoryCatalogIndex())


@pytest.mark.asyncio
async def test_clean_unique_read_resolves_confidently(resolver: CardResolver) -> None:
    result = await resolver.resolve(
        CardRead(collector_number="8/120", name="Tidecaller Leviath", quality=0.97)
    )
    assert result.candidates[0].identity.canonical_id == "origins-8"
    # A clean, unambiguous read clears the confirm threshold → the flow may commit it.
    assert not result.needs_confirmation(_CONFIRM_THRESHOLD)


@pytest.mark.asyncio
async def test_numerator_only_read_of_a_reprint_routes_to_confirm(resolver: CardResolver) -> None:
    # The number's set-total was lost (common OCR miss); two same-name printings share the
    # numerator, so neither pins — this must surface as a top-2 confirm, never a silent guess.
    result = await resolver.resolve(
        CardRead(collector_number="12", name="Emberwyrm Sovereign", quality=1.0)
    )
    ids = {c.identity.canonical_id for c in result.candidates}
    assert ids == {"origins-12", "echo-12"}
    assert result.needs_confirmation(_CONFIRM_THRESHOLD)


@pytest.mark.asyncio
async def test_full_number_pins_the_right_reprint(resolver: CardResolver) -> None:
    result = await resolver.resolve(
        CardRead(collector_number="12/120", name="Emberwyrm Sovereign", quality=0.96)
    )
    assert result.candidates[0].identity.canonical_id == "origins-12"
    assert not result.needs_confirmation(_CONFIRM_THRESHOLD)
    # The wrong-set reprint is still recalled (shared name) but scores far below.
    echo = next(c for c in result.candidates if c.identity.canonical_id == "echo-12")
    assert echo.confidence < result.candidates[0].confidence


@pytest.mark.asyncio
async def test_no_signal_is_an_empty_unrecognized_result(resolver: CardResolver) -> None:
    result = await resolver.resolve(CardRead(quality=0.9))
    assert result.candidates == []


@pytest.mark.asyncio
async def test_poor_capture_caps_confidence_even_on_an_exact_match(resolver: CardResolver) -> None:
    # Same exact read as the confident case, but a smeared capture: quality is the ceiling,
    # so even a perfect catalog match can't claim a confident identification.
    result = await resolver.resolve(
        CardRead(collector_number="8/120", name="Tidecaller Leviath", quality=0.3)
    )
    assert result.candidates[0].identity.canonical_id == "origins-8"
    assert result.needs_confirmation(_CONFIRM_THRESHOLD)
