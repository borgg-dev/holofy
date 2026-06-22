"""The artwork+OCR fusion scorer — the safety-critical decision logic.

Pure and deterministic: ``ImageMatch`` objects (a catalog identity + a Hamming distance) and a
``CardRead`` go in, a ranked ``RecognitionResult`` comes out. The tests pin the behaviours the
product turns on — a clear unique-art win commits, a same-art reprint pair with no
distinguishing number is held below the commit threshold (ADR 0002), and a read number that
pins one reprint lets it commit and overtake the art-nearest rival.
"""

from __future__ import annotations

from app.identify.catalog import CardRead
from app.identify.image_index import ImageMatch
from app.identify.visual_resolver import VisualCardResolver
from app.schemas.cards import CardIdentity, Variant

_CONFIRM_THRESHOLD = 0.70
_FLOOR = 0.35


def _identity(canonical_id: str, name: str, set_name: str, number: str) -> CardIdentity:
    return CardIdentity(
        canonical_id=canonical_id,
        name=name,
        set_name=set_name,
        collector_number=number,
        language="en",
        variant=Variant.HOLO,
    )


_CHARIZARD = _identity("base1-4", "Charizard", "Base Set", "4/102")
# Same artwork, two printings — separable only by number+set (the ADR 0002 disambiguation case).
_EMBER_A = _identity("origins-12", "Emberwyrm Sovereign", "Origins Vault", "12/120")
_EMBER_B = _identity("echo-12", "Emberwyrm Sovereign", "Echo Reprint", "12/95")


def test_clear_unique_art_match_commits() -> None:
    matches = [ImageMatch(_CHARIZARD, distance=3), ImageMatch(_EMBER_A, distance=16)]
    result = VisualCardResolver().resolve(matches, CardRead(name="Charizard"), quality=0.8)

    assert result.candidates[0].identity.canonical_id == "base1-4"
    assert not result.needs_confirmation(_CONFIRM_THRESHOLD)


def test_same_art_reprint_pair_without_number_routes_to_confirm() -> None:
    # Identical artwork → equal distance; no number read to separate them.
    matches = [ImageMatch(_EMBER_A, distance=4), ImageMatch(_EMBER_B, distance=4)]
    result = VisualCardResolver().resolve(matches, CardRead(name="Emberwyrm"), quality=0.85)

    top = result.candidates[0]
    assert result.needs_confirmation(_CONFIRM_THRESHOLD), "a reprint tie must not silently commit"
    assert top.confidence >= _FLOOR, "but it is a real recognition — surface it for confirmation"
    # The two printings stay close — the UI shows both with their price delta.
    assert abs(result.candidates[0].confidence - result.candidates[1].confidence) < 0.12


def test_collector_number_pins_a_reprint_and_lets_it_commit() -> None:
    # Art ties the pair, but the read pins 12/95 exactly — it must win and clear the threshold,
    # even though it was not the art-nearest entry in the input order.
    matches = [ImageMatch(_EMBER_A, distance=4), ImageMatch(_EMBER_B, distance=4)]
    read = CardRead(name="Emberwyrm", collector_number="12/95")
    result = VisualCardResolver().resolve(matches, read, quality=0.85)

    assert result.candidates[0].identity.canonical_id == "echo-12"
    assert not result.needs_confirmation(_CONFIRM_THRESHOLD)


def test_numerator_only_read_does_not_pin_a_reprint() -> None:
    # A bare numerator (12) matches both printings' numerator → it narrows but cannot pin, so the
    # pair stays in the confirm band rather than committing one (ADR 0002).
    matches = [ImageMatch(_EMBER_A, distance=4), ImageMatch(_EMBER_B, distance=4)]
    read = CardRead(name="Emberwyrm", collector_number="12")
    result = VisualCardResolver().resolve(matches, read, quality=0.85)

    assert result.needs_confirmation(_CONFIRM_THRESHOLD)


def test_low_localization_quality_caps_confidence() -> None:
    clear = [ImageMatch(_CHARIZARD, distance=3), ImageMatch(_EMBER_A, distance=16)]
    good = VisualCardResolver().resolve(clear, CardRead(name="Charizard"), quality=0.9)
    poor = VisualCardResolver().resolve(clear, CardRead(name="Charizard"), quality=0.1)

    assert poor.candidates[0].confidence < good.candidates[0].confidence


def test_empty_matches_yield_no_candidates() -> None:
    result = VisualCardResolver().resolve([], CardRead(name="Charizard"), quality=0.9)
    assert result.candidates == []
