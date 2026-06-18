"""Coverage for the mock authenticity provider and its config-driven factory selection."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.config import AuthenticityBackend, Settings
from app.providers.authenticity.mock import MockAuthenticityProvider
from app.providers.factory import build_authenticity_provider
from app.schemas.authenticity import SignalKind, SignalObservation


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


def test_factory_defaults_to_mock_authenticity_backend() -> None:
    assert isinstance(build_authenticity_provider(Settings()), MockAuthenticityProvider)


def test_factory_honours_authenticity_backend_enum() -> None:
    settings = Settings(authenticity_provider=AuthenticityBackend.MOCK)
    assert isinstance(build_authenticity_provider(settings), MockAuthenticityProvider)
