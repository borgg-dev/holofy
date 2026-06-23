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


# EN·FR twins: same artwork, *same* collector number, separable only by the printed name.
_PIKA_EN = _identity("base-en", "Pikachu", "Base Set", "58/102")
_PIKA_FR = _identity("base-fr", "Pikachu", "Base Set", "58/102")
_PIKA_OTHER = _identity("xy-130", "Pikachu", "XY", "87/130")  # a different, unrelated Pikachu print
# EN·FR twins whose *names* differ (the language-discriminable case).
_CHARIZARD_EN = _identity("base-en-4", "Charizard", "Base Set", "4/102")
_DRACAUFEU_FR = _identity("base-fr-4", "Dracaufeu", "Base Set", "4/102")


def test_ambiguous_top_caps_whole_list_so_a_lower_card_cannot_leapfrog() -> None:
    # The correct printing (58/102) appears as an EN·FR twin pair that ties on art+number+name and
    # so is held for confirmation. A third, unrelated 87/130 print sits just below them. The gate
    # must cap the WHOLE result, or that lower card keeps a high score and leapfrogs the capped
    # leaders into a wrong auto-commit (the real regression this guards).
    matches = [
        ImageMatch(_PIKA_EN, distance=4),
        ImageMatch(_PIKA_FR, distance=4),
        ImageMatch(_PIKA_OTHER, distance=4),
    ]
    read = CardRead(name="Pikachu", collector_number="58/102")
    result = VisualCardResolver().resolve(matches, read, quality=0.85)

    assert result.needs_confirmation(_CONFIRM_THRESHOLD), "an ambiguous twin pair must not auto-commit"
    # The correct printing (58/102), not the unrelated 87/130, must lead the confirm list.
    assert result.candidates[0].identity.collector_number == "58/102"
    assert all(c.confidence <= 0.6 + 1e-9 for c in result.candidates), "nothing escapes the confirm band"


def test_discriminative_name_commits_the_right_language_print() -> None:
    # The French print "Dracaufeu" and the English "Charizard" share the artwork AND the 4/102
    # number — only the name separates them. A confident OCR name read of "Dracaufeu" must pin the
    # French print and commit it (the EN twin cannot, because its name doesn't match the read).
    matches = [ImageMatch(_CHARIZARD_EN, distance=4), ImageMatch(_DRACAUFEU_FR, distance=4)]
    result = VisualCardResolver().resolve(matches, CardRead(name="Dracaufeu"), quality=0.85)

    assert result.candidates[0].identity.canonical_id == "base-fr-4"
    assert not result.needs_confirmation(_CONFIRM_THRESHOLD)


def test_same_name_twins_without_language_signal_stay_in_confirm() -> None:
    # When the names match across languages ("Pikachu" = "Pikachu") nothing discriminates EN from
    # FR, so an honest result confirms rather than guessing a market/price.
    matches = [ImageMatch(_PIKA_EN, distance=4), ImageMatch(_PIKA_FR, distance=4)]
    result = VisualCardResolver().resolve(matches, CardRead(name="Pikachu", collector_number="58/102"), quality=0.85)

    assert result.needs_confirmation(_CONFIRM_THRESHOLD)


def test_low_localization_quality_caps_confidence() -> None:
    clear = [ImageMatch(_CHARIZARD, distance=3), ImageMatch(_EMBER_A, distance=16)]
    good = VisualCardResolver().resolve(clear, CardRead(name="Charizard"), quality=0.9)
    poor = VisualCardResolver().resolve(clear, CardRead(name="Charizard"), quality=0.1)

    assert poor.candidates[0].confidence < good.candidates[0].confidence


def test_empty_matches_yield_no_candidates() -> None:
    result = VisualCardResolver().resolve([], CardRead(name="Charizard"), quality=0.9)
    assert result.candidates == []
