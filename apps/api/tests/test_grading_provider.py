"""Coverage for the mock grading provider and its config-driven factory selection."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.config import GradingBackend, Settings
from app.providers.factory import build_grading_provider
from app.providers.grading.mock import MockGradingProvider
from app.schemas.grading import GradingAxis


@dataclass
class _Capture:
    capture_ref: str
    image_count: int = 1


@pytest.mark.asyncio
async def test_grade_returns_the_three_bought_axes_only() -> None:
    sub_scores = await MockGradingProvider().grade(_Capture("mock-gem"))

    axes = {s.axis for s in sub_scores}
    # Centering is measured in-house and must never come back from the bought provider.
    assert axes == {GradingAxis.CORNERS, GradingAxis.EDGES, GradingAxis.SURFACE}
    assert GradingAxis.CENTERING not in axes


@pytest.mark.asyncio
async def test_gem_fixture_is_high_score_and_high_confidence() -> None:
    sub_scores = await MockGradingProvider().grade(_Capture("mock-gem"))
    assert all(s.score >= 9.0 for s in sub_scores)
    assert all(s.confidence > 0.85 for s in sub_scores)


@pytest.mark.asyncio
async def test_poor_surface_fixture_is_low_score_but_still_confident() -> None:
    # The honesty case: a confidently-read poor surface — a low score is not a low-confidence
    # read, so the composite can drag the range down without diluting its certainty.
    sub_scores = await MockGradingProvider().grade(_Capture("mock-poor-surface"))
    surface = next(s for s in sub_scores if s.axis is GradingAxis.SURFACE)
    assert surface.score < 5.0
    assert surface.confidence > 0.85


@pytest.mark.asyncio
async def test_low_confidence_fixture_reports_low_confidence() -> None:
    sub_scores = await MockGradingProvider().grade(_Capture("mock-low-confidence"))
    assert all(s.confidence < 0.5 for s in sub_scores)


@pytest.mark.asyncio
async def test_unknown_capture_defaults_to_low_confidence_case() -> None:
    sub_scores = await MockGradingProvider().grade(_Capture("anything-else"))
    assert all(s.confidence < 0.5 for s in sub_scores)


def test_factory_defaults_to_mock_grading_backend() -> None:
    assert isinstance(build_grading_provider(Settings()), MockGradingProvider)


def test_factory_honours_grading_backend_enum() -> None:
    settings = Settings(grading_provider=GradingBackend.MOCK)
    assert isinstance(build_grading_provider(settings), MockGradingProvider)
