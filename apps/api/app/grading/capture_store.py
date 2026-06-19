"""Resolving a capture reference to the image bytes the pre-grade measures.

The pre-grade endpoint, like the scan endpoint, takes a *reference* to an already-uploaded
capture, never the bytes — stills live in object storage (data minimization, §6). Centering
genuinely needs pixels though, so this seam resolves a ``capture_ref`` to bytes.

``CaptureStore`` is the Protocol the real object-storage (EU-region S3/GCS) client drops in
behind. The mock synthesises deterministic, labelled card images keyed on the ref — exactly
mirroring how ``MockRecognitionProvider`` keys fixtures on ``bundle_id`` — so the whole
pre-grade flow runs with no storage and no network, and tests can drive a centred card, an
off-centre card, and an ungradeable full-bleed card by reference alone.
"""

from __future__ import annotations

from io import BytesIO
from typing import Final, Protocol

import numpy as np

# The canonical "this reference resolves to nothing" error lives at the storage layer, where
# a ref is actually resolved; re-exported here so existing callers (the pre-grade endpoint)
# keep catching ``app.grading.capture_store.CaptureNotFoundError`` unchanged.
from app.storage.base import CaptureNotFoundError

__all__ = ["CaptureNotFoundError", "CaptureStore", "MockCaptureStore"]


class CaptureStore(Protocol):
    async def load(self, capture_ref: str) -> bytes:
        """Return the encoded image bytes for a capture reference."""
        ...


# capture_ref → border widths (left, right, top, bottom) of a synthetic bordered card, or
# ``None`` for a full-bleed card with no measurable frame (the refuse-path fixture).
_FIXTURES: Final[dict[str, tuple[int, int, int, int] | None]] = {
    "capture-centered": (40, 40, 40, 40),  # pristine, high confidence → confident range
    "capture-off-center": (60, 20, 45, 45),  # 75/25 L-R → a visibly lower, wide range
    "capture-full-bleed": None,  # no inner border → centering refuses → retake
}

_DEFAULT_CAPTURE = "capture-centered"


class MockCaptureStore:
    """Deterministic synthetic captures keyed on the reference — no storage, no network."""

    async def load(self, capture_ref: str) -> bytes:
        if capture_ref not in _FIXTURES and not capture_ref.startswith("capture-"):
            # Unknown but plausibly-shaped refs fall back to a centred card so a caller that
            # just wants a happy-path estimate need not know the fixture names; a ref that
            # isn't a capture at all is a genuine miss.
            raise CaptureNotFoundError(capture_ref)
        borders = _FIXTURES.get(capture_ref, _FIXTURES[_DEFAULT_CAPTURE])
        return _encode_png(_render_card(borders))


def _render_card(borders: tuple[int, int, int, int] | None) -> np.ndarray:
    """Render a synthetic bordered (or full-bleed) card on a contrasting background.

    Same construction as the centering test synthetics: an outer light card on a dark
    surface, with a darker inner art panel at the given border widths. ``None`` borders
    produce a uniform full-bleed face the centering measurement honestly can't read.
    """
    height, width, margin = 700, 500, 24
    background, card_value, art_value = 30.0, 235.0, 90.0

    field = np.full((height, width), background, dtype=np.float64)
    top, bottom, left, right = margin, height - margin, margin, width - margin
    field[top:bottom, left:right] = card_value

    if borders is not None:
        b_left, b_right, b_top, b_bottom = borders
        field[top + b_top : bottom - b_bottom, left + b_left : right - b_right] = art_value

    return field.astype(np.uint8)


def _encode_png(field: np.ndarray) -> bytes:
    from PIL import Image

    buffer = BytesIO()
    Image.fromarray(field, mode="L").save(buffer, format="PNG")
    return buffer.getvalue()
