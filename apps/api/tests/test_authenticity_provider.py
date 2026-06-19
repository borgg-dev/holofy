"""Coverage for the mock authenticity provider and its config-driven factory selection."""

from __future__ import annotations

import re
from dataclasses import dataclass

import pytest

from app.config import AuthenticityBackend, Settings
from app.providers.authenticity.mock import MockAuthenticityProvider
from app.providers.factory import build_authenticity_provider
from app.schemas.authenticity import SignalDetail, SignalKind, SignalObservation


@dataclass
class _Capture:
    capture_ref: str
    image_count: int = 1


@pytest.mark.asyncio
async def test_analyze_returns_the_four_visual_signals_only() -> None:
    signals = await MockAuthenticityProvider().analyze(_Capture("capture-authentic"))

    kinds = {s.kind for s in signals}
    assert kinds == {
        SignalKind.PRINT_PATTERN,
        SignalKind.HOLO_SIGNATURE,
        SignalKind.FONT_LAYOUT,
        SignalKind.CARDSTOCK,
    }
    # The catalog cross-check is the service's deterministic lookup, never a provider read.
    assert SignalKind.CATALOG_EXISTENCE not in kinds


@pytest.mark.asyncio
async def test_authentic_fixture_reads_consistent_and_confident() -> None:
    signals = await MockAuthenticityProvider().analyze(_Capture("capture-authentic"))
    assert all(s.observation is SignalObservation.CONSISTENT for s in signals)
    assert all(s.confidence > 0.85 for s in signals)


@pytest.mark.asyncio
async def test_mixed_fixture_has_deviating_signals_at_solid_confidence() -> None:
    # The honesty case: deviating signals read confidently — a deviation is evidence, not a
    # low-confidence read, so the composite can lean toward risk without diluting certainty.
    signals = await MockAuthenticityProvider().analyze(_Capture("capture-mixed"))
    deviations = [s for s in signals if s.observation is SignalObservation.DEVIATION]
    assert deviations
    assert all(s.confidence > 0.8 for s in deviations)


@pytest.mark.asyncio
async def test_poor_fixture_is_unreadable_at_low_confidence() -> None:
    signals = await MockAuthenticityProvider().analyze(_Capture("capture-poor"))
    assert any(s.observation is SignalObservation.UNREADABLE for s in signals)
    assert all(s.confidence < 0.4 for s in signals)


@pytest.mark.asyncio
async def test_unknown_capture_defaults_to_the_poor_case() -> None:
    signals = await MockAuthenticityProvider().analyze(_Capture("anything-else"))
    assert all(s.confidence < 0.4 for s in signals)


# Accusatory / verdict-shaped language the per-signal detail must never carry — the §3.5 gate
# at the sentence level. A real provider can only *select* from ``SignalDetail``, so banning
# these tokens from the whole vocabulary makes an accusatory sentence physically impossible.
_BANNED_DETAIL_TOKENS = (
    "fake",
    "faked",
    "counterfeit",
    "genuine",
    "authentic",
    "real",
    "replica",
    "bootleg",
    "knockoff",
    "knock-off",
    "forgery",
    "forged",
    "fraud",
)


def test_signal_detail_vocabulary_carries_no_accusatory_tokens() -> None:
    # ``detail`` is a closed vocabulary, not free text: assert no member can voice an
    # accusation or a verdict, so no provider (mock or real) can emit one through this seam.
    # Matched on word boundaries — "professional authentication" (the honest next step) is
    # fine; a bare "authentic"/"counterfeit" claim about the card is not.
    for member in SignalDetail:
        phrase = member.value.lower()
        for token in _BANNED_DETAIL_TOKENS:
            assert not re.search(rf"\b{re.escape(token)}\b", phrase), (
                f"{member.name} contains banned token {token!r}"
            )


def test_signal_detail_is_a_closed_set_not_free_text() -> None:
    # The field rejects any string outside the reviewed vocabulary — the structural guarantee
    # that a future real provider physically can't author an accusatory sentence.
    from pydantic import ValidationError

    from app.schemas.authenticity import AuthenticitySignal

    accusatory: object = "This card is a counterfeit."
    with pytest.raises(ValidationError):
        AuthenticitySignal(
            kind=SignalKind.PRINT_PATTERN,
            observation=SignalObservation.DEVIATION,
            confidence=0.9,
            detail=accusatory,
        )


class _FakeStore:
    async def load(self, ref: str) -> bytes:  # pragma: no cover - not called by the factory
        raise NotImplementedError


def test_factory_defaults_to_inhouse_authenticity_backend() -> None:
    # The production default is the real, pixel-reading in-house analyzer — no mock ships.
    from app.providers.authenticity.inhouse import InHouseAuthenticityProvider

    provider = build_authenticity_provider(Settings(), _FakeStore())
    assert isinstance(provider, InHouseAuthenticityProvider)


def test_factory_honours_authenticity_backend_enum() -> None:
    settings = Settings(authenticity_provider=AuthenticityBackend.MOCK)
    assert isinstance(
        build_authenticity_provider(settings, _FakeStore()), MockAuthenticityProvider
    )
