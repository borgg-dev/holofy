"""Unit coverage for the frame-budget arithmetic.

These pin the design boundaries the spike actually leans on — the frame-interval
cap, the min() ceiling on preview FPS, the dwell-bound stack-throughput cliff,
and the sample-rate inversion — not any particular sourced latency, which is an
input to the model rather than part of it.
"""

from __future__ import annotations

import pytest

from fps_budget import (
    InferenceProfile,
    StackScanModel,
    fits_frame_budget,
    required_sample_fps,
    sustained_preview_fps,
)


def test_total_includes_pre_and_post() -> None:
    p = InferenceProfile("x", inference_ms=6.0, preprocess_ms=3.0, postprocess_ms=1.0)
    assert p.total_ms() == 10.0
    assert p.achievable_fps() == 100.0


def test_zero_or_negative_total_rejected() -> None:
    with pytest.raises(ValueError):
        InferenceProfile("bad", inference_ms=0.0).total_ms()


def test_preview_fps_capped_by_camera_not_model() -> None:
    # A 7 ms model could run ~142 FPS but a 30 FPS camera caps it at 30.
    fast = InferenceProfile("ne", inference_ms=7.0)
    assert sustained_preview_fps(fast, camera_fps=30) == 30.0


def test_preview_fps_capped_by_model_when_slow() -> None:
    # A 50 ms/frame model (20 FPS) cannot keep a 30 FPS camera full.
    slow = InferenceProfile("cpu", inference_ms=50.0)
    assert sustained_preview_fps(slow, camera_fps=30) == pytest.approx(20.0)


def test_frame_budget_boundary_30fps() -> None:
    # 33.33 ms is the 30 FPS interval; 33 ms fits, 34 ms drops frames.
    assert fits_frame_budget(InferenceProfile("a", inference_ms=33.0), 30)
    assert not fits_frame_budget(InferenceProfile("b", inference_ms=34.0), 30)


def test_unsupported_camera_fps_rejected() -> None:
    with pytest.raises(ValueError):
        sustained_preview_fps(InferenceProfile("x", inference_ms=5.0), camera_fps=24)


def test_stack_confirms_when_dwell_supplies_enough_frames() -> None:
    # 800 ms dwell, 8 FPS sampling, 70% pass => 800/1000*8*0.7 = 4.48 confirmable
    # frames, enough for a 3-frame confirm.
    m = StackScanModel(sample_fps=8.0, card_dwell_ms=800.0, frames_to_confirm=3)
    assert m.can_confirm()
    assert m.confirmable_frames_per_card() == pytest.approx(4.48)
    assert m.cards_per_minute() == pytest.approx(75.0)


def test_stack_throughput_collapses_when_fanned_too_fast() -> None:
    # 200 ms dwell at 8 FPS, 70% pass => 1.12 confirmable frames < 3 required.
    m = StackScanModel(sample_fps=8.0, card_dwell_ms=200.0, frames_to_confirm=3)
    assert not m.can_confirm()
    assert m.cards_per_minute() == 0.0


def test_required_sample_fps_inverts_the_dwell_model() -> None:
    # To land 3 confirmable frames in an 800 ms window at 70% pass-rate you need
    # 3 / (0.8 * 0.7) ~= 5.36 FPS sampling — comfortably below 30 FPS.
    fps = required_sample_fps(card_dwell_ms=800.0, frames_to_confirm=3)
    assert fps == pytest.approx(5.357, rel=1e-3)


def test_required_sample_fps_validates_inputs() -> None:
    with pytest.raises(ValueError):
        required_sample_fps(card_dwell_ms=0.0, frames_to_confirm=3)
    with pytest.raises(ValueError):
        required_sample_fps(card_dwell_ms=800.0, frames_to_confirm=3, confirm_success_rate=0)
