"""Coverage for the in-house visual authenticity analyzer (real pixels → readability reads).

The load-bearing invariant: from a phone capture, with no per-card genuine reference yet, the
analyzer never asserts a visual signal is ``consistent`` or ``deviation`` — it only reports
whether the capture could *read* each cue. The dispositive risk signal is the catalog
cross-check elsewhere; these tests pin that the visual stage stays honest.
"""

from __future__ import annotations

from io import BytesIO

import numpy as np
import pytest
from PIL import Image

from app.authenticity.visual import assess_visual_signals
from app.providers.authenticity.inhouse import InHouseAuthenticityProvider
from app.schemas.authenticity import SignalKind, SignalObservation


def _sharp_card_png(short_side: int = 600) -> bytes:
    """A high-res, sharp, glare-free card-shaped capture: bordered panel + fine interior
    texture so the gradient-energy focus proxy reads as resolvable, in card aspect (~0.71)."""
    height = short_side
    width = int(round(short_side * 0.716))
    rng = np.random.default_rng(7)
    arr = np.full((height, width, 3), 30, dtype=np.uint8)  # dark surround
    # Bright card body with mid-range textured interior (no blown-out glare).
    arr[20:-20, 20:-20] = 200
    interior = rng.integers(60, 190, size=(height - 80, width - 80, 3), dtype=np.uint8)
    arr[40:-40, 40:-40] = interior
    buf = BytesIO()
    Image.fromarray(arr, mode="RGB").save(buf, format="PNG")
    return buf.getvalue()


def _visual_kinds(signals) -> set[SignalKind]:  # noqa: ANN001
    return {s.kind for s in signals}


def test_returns_the_four_visual_signals_never_the_catalog_signal() -> None:
    signals = assess_visual_signals(_sharp_card_png(), image_count=1)
    assert _visual_kinds(signals) == {
        SignalKind.PRINT_PATTERN,
        SignalKind.HOLO_SIGNATURE,
        SignalKind.FONT_LAYOUT,
        SignalKind.CARDSTOCK,
    }
    assert SignalKind.CATALOG_EXISTENCE not in _visual_kinds(signals)


def test_visual_signals_never_assert_consistent_or_deviation() -> None:
    # The honesty invariant: with no reference comparator, a visual read is only ever
    # "readable but inconclusive" or "unreadable" — never a genuine/diverges-from-genuine call.
    for image_count in (1, 2, 4):
        for image in (_sharp_card_png(), _sharp_card_png(320), b"not-an-image"):
            for s in assess_visual_signals(image, image_count=image_count):
                assert s.observation in {
                    SignalObservation.INCONCLUSIVE,
                    SignalObservation.UNREADABLE,
                }


def test_undecodable_bytes_are_all_unreadable() -> None:
    signals = assess_visual_signals(b"\x00\x01garbage", image_count=3)
    assert all(s.observation is SignalObservation.UNREADABLE for s in signals)
    assert all(s.confidence < 0.4 for s in signals)


def test_holo_needs_multiple_angles() -> None:
    holo_single = _holo(assess_visual_signals(_sharp_card_png(), image_count=1))
    assert holo_single.observation is SignalObservation.UNREADABLE

    holo_multi = _holo(assess_visual_signals(_sharp_card_png(), image_count=3))
    assert holo_multi.observation is SignalObservation.INCONCLUSIVE


def test_sharp_capture_resolves_print_and_layout() -> None:
    signals = {s.kind: s for s in assess_visual_signals(_sharp_card_png(), image_count=1)}
    assert signals[SignalKind.PRINT_PATTERN].observation is SignalObservation.INCONCLUSIVE
    assert signals[SignalKind.FONT_LAYOUT].observation is SignalObservation.INCONCLUSIVE
    # Confidence stays modest — a v1 read without a reference is never authoritative.
    assert all(0.0 < s.confidence <= 0.7 for s in signals.values())


@pytest.mark.asyncio
async def test_inhouse_provider_reads_from_the_capture_store() -> None:
    class _Store:
        async def load(self, ref: str) -> bytes:
            return _sharp_card_png()

    class _Capture:
        capture_ref = "ref-1"
        image_count = 3

    signals = await InHouseAuthenticityProvider(_Store()).analyze(_Capture())
    assert _visual_kinds(signals) == {
        SignalKind.PRINT_PATTERN,
        SignalKind.HOLO_SIGNATURE,
        SignalKind.FONT_LAYOUT,
        SignalKind.CARDSTOCK,
    }


def _holo(signals):  # noqa: ANN001
    return next(s for s in signals if s.kind is SignalKind.HOLO_SIGNATURE)
