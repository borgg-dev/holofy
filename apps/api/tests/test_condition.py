"""The in-house condition reader. Proves it genuinely measures defects from pixels (not a
fixture): a clean card reads high on every axis, and adding real wear/damage to a region
drops *that* axis's score — with honestly modest confidence, as befits a v1 heuristic.
"""

from __future__ import annotations

from io import BytesIO

import numpy as np
import pytest
from PIL import Image

from app.grading.condition import assess_condition
from app.providers.grading.inhouse import InHouseGradingProvider
from app.schemas.grading import GradingAxis
from app.storage.memory import InMemoryCaptureStorage

_RNG = np.random.default_rng(7)


def _card(*, edge_noise: bool = False, surface_noise: bool = False) -> bytes:
    # A mid-tone card filling a dark frame so detection crops to the card.
    arr = np.full((520, 380, 3), 12, dtype=np.uint8)
    card = np.full((460, 320, 3), 150, dtype=np.uint8)
    if surface_noise:
        # Scratches/print-lines across the face: bright streaks the reader should see.
        for y in _RNG.integers(20, 440, size=40):
            card[int(y), 10:310] = 255
    arr[30:490, 30:350] = card
    if edge_noise:
        # Whitening/fraying along the card's top edge band.
        speckle = _RNG.integers(0, 2, size=(10, 320)) * 255
        arr[30:40, 30:350] = np.stack([speckle] * 3, axis=-1).astype(np.uint8)
    buffer = BytesIO()
    Image.fromarray(arr).save(buffer, format="PNG")
    return buffer.getvalue()


def test_clean_card_reads_high_on_every_axis() -> None:
    reads = assess_condition(_card())
    for axis in (GradingAxis.CORNERS, GradingAxis.EDGES, GradingAxis.SURFACE):
        assert reads[axis].score >= 9.0, axis
        # Honest v1: confident enough to be useful, never claiming certainty.
        assert 0.2 <= reads[axis].confidence <= 0.85


def test_edge_damage_lowers_the_edge_score() -> None:
    clean = assess_condition(_card())
    worn = assess_condition(_card(edge_noise=True))
    assert worn[GradingAxis.EDGES].score < clean[GradingAxis.EDGES].score


def test_surface_damage_lowers_the_surface_score() -> None:
    clean = assess_condition(_card())
    scratched = assess_condition(_card(surface_noise=True))
    assert scratched[GradingAxis.SURFACE].score < clean[GradingAxis.SURFACE].score


@pytest.mark.asyncio
async def test_inhouse_provider_grades_a_stored_capture() -> None:
    store = InMemoryCaptureStorage()
    ref = await store.save([_card()])

    from dataclasses import dataclass

    @dataclass
    class _Capture:
        capture_ref: str
        image_count: int = 1

    sub_scores = await InHouseGradingProvider(store).grade(_Capture(ref))
    axes = {s.axis for s in sub_scores}
    # The bought axes only — centering is measured separately, never from this provider.
    assert axes == {GradingAxis.CORNERS, GradingAxis.EDGES, GradingAxis.SURFACE}
