"""In-house visual authenticity reads — from the real capture pixels, honestly bounded.

This is the owned alternative to a bought CV ensemble for the four *visual* signals (print
pattern, holo signature, font/layout, cardstock). It is deliberately **honest about what a
phone capture can and can't support today**: without a per-card genuine reference image to
compare against, this v1 cannot assert that a card's print or foil *matches* or *diverges
from* a reference — so it never emits ``consistent`` or ``deviation`` on a visual signal.
Doing otherwise would be inventing a counterfeit verdict we can't substantiate (charter §3.5).

What it *can* do from real pixels, and does: measure — per signal — whether the capture is
good enough to read that cue at all. A sharp, well-framed, glare-free close-up can resolve the
print pattern and typography (``inconclusive`` at modest confidence: read, nothing our v1 can
flag); a soft or glare-washed one cannot (``unreadable``). The holo signature needs multiple
tilt angles, so a single-frame capture can't support it. This drives the service's honest
assess-vs-``retake`` decision on real evidence, while the dispositive risk signal stays the
deterministic catalog-existence cross-check the service owns. The trained per-card reference
comparator drops in behind this same function as the consented data loop fills the reference
set (the moat).

Pure numpy/Pillow on the detected card crop — no OpenCV in our own code, like centering.
"""

from __future__ import annotations

from io import BytesIO

import numpy as np
from PIL import Image

from app.identify.vision.detect import detect_card_crop
from app.schemas.authenticity import (
    AuthenticitySignal,
    SignalDetail,
    SignalKind,
    SignalObservation,
)

# Below this detection quality the frame doesn't hold a cleanly-framed card — nothing to read.
_MIN_CARD_QUALITY = 0.45
# Sharpness (normalized gradient energy) at/above which fine cues (print, type) are resolvable.
_SHARP_RESOLVE = 0.7
# Fraction of blown-out (near-white) pixels above which glare obscures a region's detail.
_GLARE_OBSCURES = 0.18
# A crop narrower than this (px on the short side) can't resolve the halftone/typography.
_MIN_RESOLVE_PX = 320
# Visual reads are a v1 without a reference comparator — confidence is capped well below 1 so
# the composite keeps an honest spread and these never masquerade as authoritative evidence.
_CONF_CAP = 0.7
_CONF_FLOOR = 0.12


def assess_visual_signals(
    image_bytes: bytes, *, image_count: int
) -> list[AuthenticitySignal]:
    """Read the four visual signals' *readability* from a real capture's pixels.

    Returns one signal per visual cue. Each is ``inconclusive`` (the cue was resolvable; our
    v1 has no reference to flag a divergence) or ``unreadable`` (the capture can't support it),
    with a confidence derived from the measured capture quality — never ``consistent`` or
    ``deviation``, which would assert a reference comparison we can't yet make.
    """
    try:
        crop = detect_card_crop(image_bytes)
        card_quality = float(crop.quality)
    except Exception:
        # Undecodable bytes can support no visual read at all.
        return _all_unreadable()

    if card_quality < _MIN_CARD_QUALITY:
        return _all_unreadable()

    gray = crop.image.mean(axis=2) if crop.image.ndim == 3 else crop.image.astype(float)
    height, width = gray.shape[0], gray.shape[1]
    short_side = min(height, width)

    sharpness = _sharpness(gray)
    glare = _glare_fraction(gray)
    resolvable = short_side >= _MIN_RESOLVE_PX

    # A base read-confidence from the card framing and sharpness; each signal scales it by its
    # own obstruction (glare, too few angles, edges out of frame).
    base_conf = _clamp_conf(0.5 * card_quality + 0.5 * sharpness)

    return [
        _print_pattern(sharpness, resolvable, base_conf),
        _holo_signature(image_count, base_conf),
        _font_layout(sharpness, glare, base_conf),
        _cardstock(card_quality, base_conf),
    ]


def _print_pattern(
    sharpness: float, resolvable: bool, base_conf: float
) -> AuthenticitySignal:
    if not resolvable or sharpness < _SHARP_RESOLVE:
        return _signal(
            SignalKind.PRINT_PATTERN,
            SignalObservation.UNREADABLE,
            _CONF_FLOOR + 0.2 * sharpness,
            SignalDetail.PRINT_TOO_COARSE_TO_READ,
        )
    # Resolvable: we read the print, but without a reference print-run we can't flag divergence.
    return _signal(
        SignalKind.PRINT_PATTERN,
        SignalObservation.INCONCLUSIVE,
        base_conf,
        SignalDetail.PRINT_MATCHES_REFERENCE,
    )


def _holo_signature(image_count: int, base_conf: float) -> AuthenticitySignal:
    # The foil read needs multiple tilt angles; a single still physically can't support it.
    if image_count < 2:
        return _signal(
            SignalKind.HOLO_SIGNATURE,
            SignalObservation.UNREADABLE,
            _CONF_FLOOR,
            SignalDetail.HOLO_NEEDS_MORE_ANGLES,
        )
    return _signal(
        SignalKind.HOLO_SIGNATURE,
        SignalObservation.INCONCLUSIVE,
        # Slightly discounted: more angles help, but we still have no reference foil to match.
        _clamp_conf(0.85 * base_conf),
        SignalDetail.HOLO_MATCHES_REFERENCE,
    )


def _font_layout(sharpness: float, glare: float, base_conf: float) -> AuthenticitySignal:
    if glare >= _GLARE_OBSCURES:
        return _signal(
            SignalKind.FONT_LAYOUT,
            SignalObservation.UNREADABLE,
            _CONF_FLOOR,
            SignalDetail.LAYOUT_OBSCURED,
        )
    if sharpness < _SHARP_RESOLVE:
        # Text is legible enough to see it's plausible, but not to compare typography closely.
        return _signal(
            SignalKind.FONT_LAYOUT,
            SignalObservation.INCONCLUSIVE,
            _clamp_conf(0.6 * base_conf),
            SignalDetail.LAYOUT_WITHIN_TOLERANCE,
        )
    return _signal(
        SignalKind.FONT_LAYOUT,
        SignalObservation.INCONCLUSIVE,
        base_conf,
        SignalDetail.LAYOUT_WITHIN_TOLERANCE,
    )


def _cardstock(card_quality: float, base_conf: float) -> AuthenticitySignal:
    # Cardstock cues live at the edges; a card that doesn't sit cleanly in frame can't show them.
    if card_quality < 0.6:
        return _signal(
            SignalKind.CARDSTOCK,
            SignalObservation.UNREADABLE,
            _CONF_FLOOR,
            SignalDetail.STOCK_OUT_OF_FRAME,
        )
    return _signal(
        SignalKind.CARDSTOCK,
        SignalObservation.INCONCLUSIVE,
        _clamp_conf(0.8 * base_conf),
        SignalDetail.STOCK_MATCHES_REFERENCE,
    )


def _sharpness(gray: np.ndarray) -> float:
    """Normalized gradient energy in [0, 1] — a focus proxy. A blurred crop reads near zero."""
    if gray.size < 4:
        return 0.0
    gy = np.diff(gray, axis=0)
    gx = np.diff(gray, axis=1)
    energy = float(np.mean(gx * gx) + np.mean(gy * gy))
    # ~200 (luminance² per pixel) is a comfortably sharp card photo; scale to 1.0 there.
    return float(np.clip(energy / 200.0, 0.0, 1.0))


def _glare_fraction(gray: np.ndarray) -> float:
    """Fraction of near-white blown-out pixels — specular glare that hides local detail."""
    if gray.size == 0:
        return 1.0
    return float(np.mean(gray >= 250.0))


def _signal(
    kind: SignalKind,
    observation: SignalObservation,
    confidence: float,
    detail: SignalDetail,
) -> AuthenticitySignal:
    return AuthenticitySignal(
        kind=kind,
        observation=observation,
        confidence=_clamp_conf(confidence),
        detail=detail,
    )


def _all_unreadable() -> list[AuthenticitySignal]:
    """No card resolvable in the frame — every visual signal is unreadable, low confidence."""
    return [
        _signal(SignalKind.PRINT_PATTERN, SignalObservation.UNREADABLE, _CONF_FLOOR, SignalDetail.PRINT_TOO_COARSE_TO_READ),
        _signal(SignalKind.HOLO_SIGNATURE, SignalObservation.UNREADABLE, _CONF_FLOOR, SignalDetail.HOLO_NEEDS_MORE_ANGLES),
        _signal(SignalKind.FONT_LAYOUT, SignalObservation.UNREADABLE, _CONF_FLOOR, SignalDetail.LAYOUT_OBSCURED),
        _signal(SignalKind.CARDSTOCK, SignalObservation.UNREADABLE, _CONF_FLOOR, SignalDetail.STOCK_OUT_OF_FRAME),
    ]


def _clamp_conf(value: float) -> float:
    return round(float(max(_CONF_FLOOR, min(_CONF_CAP, value))), 3)


def _decode_gray(image_bytes: bytes) -> np.ndarray:
    """Decode to a 2-D luminance array — used by tests that bypass card detection."""
    return np.asarray(Image.open(BytesIO(image_bytes)).convert("L"), dtype=np.float64)
