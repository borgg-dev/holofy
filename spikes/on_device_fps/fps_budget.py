"""Frame-budget arithmetic for the on-device detection loop.

This is an *estimation* tool, not a benchmark. No device is available for this
spike, so we reason forward from published per-inference latencies (see
FINDINGS.md / ADR 0003 for sources) to the two numbers that actually decide the
design:

  1. the live preview FPS a detector can sustain inside a VisionCamera frame
     processor, given the frame interval it has to fit inside; and
  2. the stack-scanning throughput in *unique cards per minute*, which is gated
     by how long a card dwells in frame and how many frames we must agree on
     before we commit a card — not by raw inference speed.

Everything here is plain closed-form arithmetic so the assumptions are legible
and falsifiable against real on-device timings later.
"""

from __future__ import annotations

from dataclasses import dataclass

# A camera running at N FPS hands us a frame every (1000 / N) ms. A *synchronous*
# frame processor must return inside that window or the next frame is dropped
# (VisionCamera semantics). These are the two preview rates we design against.
FRAME_INTERVAL_MS = {30: 1000.0 / 30, 60: 1000.0 / 60}


@dataclass(frozen=True)
class InferenceProfile:
    """One measured (or, here, sourced) per-stage cost on a target device.

    Latencies are wall-clock milliseconds for a single frame, end to end within
    the named stage. `preprocess_ms` is the resize/letterbox/colour-convert cost
    that is easy to forget and routinely dominates a fast model on a slow CPU;
    `postprocess_ms` is decode + NMS.
    """

    label: str
    inference_ms: float
    preprocess_ms: float = 0.0
    postprocess_ms: float = 0.0

    def total_ms(self) -> float:
        total = self.inference_ms + self.preprocess_ms + self.postprocess_ms
        if total <= 0:
            raise ValueError(f"{self.label}: total per-frame cost must be > 0")
        return total

    def achievable_fps(self) -> float:
        """Frames per second this stage can sustain if it never waits on I/O."""
        return 1000.0 / self.total_ms()


def sustained_preview_fps(profile: InferenceProfile, camera_fps: int = 30) -> float:
    """Detector FPS actually delivered to the live preview.

    Two ceilings apply and the lower one wins: the camera cannot hand frames
    faster than `camera_fps`, and the processor cannot consume them faster than
    its own throughput. A synchronous processor that overruns the frame interval
    drops frames, so the realised rate is the model's own rate capped at the
    camera rate.
    """
    if camera_fps not in FRAME_INTERVAL_MS:
        raise ValueError(f"unsupported camera FPS {camera_fps}; expected 30 or 60")
    return min(float(camera_fps), profile.achievable_fps())


def fits_frame_budget(profile: InferenceProfile, camera_fps: int = 30) -> bool:
    """True if the stage returns within one frame interval (no dropped frames)."""
    if camera_fps not in FRAME_INTERVAL_MS:
        raise ValueError(f"unsupported camera FPS {camera_fps}; expected 30 or 60")
    return profile.total_ms() <= FRAME_INTERVAL_MS[camera_fps]


@dataclass(frozen=True)
class StackScanModel:
    """Throughput model for high-volume 'fan a stack past the lens' scanning.

    The bottleneck is physical, not computational. A card is only in frame for
    `card_dwell_ms`; we must land `frames_to_confirm` *clean* detections of the
    same card to commit it (dedupe + quality gate), and the detector samples at
    `sample_fps`. If the dwell window cannot supply that many confirmable frames,
    throughput is dwell-bound, not inference-bound.
    """

    sample_fps: float
    card_dwell_ms: float
    frames_to_confirm: int = 3
    confirm_success_rate: float = 0.7  # fraction of sampled frames that pass the quality gate

    def confirmable_frames_per_card(self) -> float:
        sampled = (self.card_dwell_ms / 1000.0) * self.sample_fps
        return sampled * self.confirm_success_rate

    def can_confirm(self) -> bool:
        return self.confirmable_frames_per_card() >= self.frames_to_confirm

    def cards_per_minute(self) -> float:
        """Sustainable unique-card commit rate.

        Dwell-bound: one card per dwell window when the window yields enough
        confirmable frames; otherwise the operator is fanning faster than we can
        safely commit and effective throughput collapses to zero committed cards
        (we'd be forcing them to slow down via the coaching UI)."""
        if not self.can_confirm():
            return 0.0
        return 60_000.0 / self.card_dwell_ms


def required_sample_fps(
    card_dwell_ms: float, frames_to_confirm: int, confirm_success_rate: float = 0.7
) -> float:
    """Minimum detector sampling rate to confirm a card within its dwell window.

    Inverts `StackScanModel`: given how long a card is visible and how many clean
    detections we insist on, what sampling FPS must the detector hold? This is the
    number that tells us whether a 5-10 FPS sampled detector is enough for stack
    mode (it usually is) without paying for 30 FPS continuous inference.
    """
    if card_dwell_ms <= 0 or frames_to_confirm <= 0:
        raise ValueError("dwell and frames_to_confirm must be positive")
    if not 0 < confirm_success_rate <= 1:
        raise ValueError("confirm_success_rate must be in (0, 1]")
    dwell_s = card_dwell_ms / 1000.0
    return frames_to_confirm / (dwell_s * confirm_success_rate)
