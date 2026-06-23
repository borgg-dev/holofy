"""Artwork reference check — does the captured card's face match the genuine reference?

The v1 visual signals could only say "readable / unreadable": with no per-card genuine reference
to compare against, they never asserted that a card's printed face *matches* a real printing. The
recognizer's learned embedding *is* that reference comparison: every catalog card is embedded, so
a capture can be embedded and compared to the genuine card's reference embedding by cosine.

It is deliberately a **reassurance-only** signal. A high match is real positive evidence (the
artwork is consistent with the genuine printing) and emits ``consistent``. A low match is *not*
emitted as ``deviation`` — a legitimate close-up or a poorly-framed capture also scores low, so
crying divergence would manufacture a false accusation (charter §3.5). Below the match bar it is
``unreadable``: it simply couldn't compare, widening uncertainty rather than counting against the
card. The accusatory signal stays the deterministic catalog-existence check the service owns.

Reuses the recognizer's rectify + embed; like the other in-house reads it works on the capture
bytes. A missing model / reference makes it an honest ``unreadable``, never an error.
"""

from __future__ import annotations

import numpy as np

from app.identify.vision.embed import EmbeddingModelUnavailable, embed
from app.identify.vision.rectify import rectify_card
from app.schemas.authenticity import (
    AuthenticitySignal,
    SignalDetail,
    SignalKind,
    SignalObservation,
)

# Cosine at/above which the captured face clearly matches the genuine reference — a real card,
# even across an EN/FR print, clears this comfortably (the recognizer's true matches sit ~0.78+).
# Below it we don't know (close-up / poor framing / — rarely — a divergent face), so we abstain.
_CONSISTENT_COSINE = 0.78
# Confidence floor/ceiling for a confirmed match — scaled by how far above the bar the match sits,
# so a borderline match is reported less certainly than a textbook one. Never 1.0: a single image.
_CONF_FLOOR = 0.5
_CONF_CEIL = 0.85


def _best_oriented_cosine(image: "np.ndarray", reference: np.ndarray, model_path: str) -> float:
    """The capture's best cosine to the reference across the four right-angle orientations (the
    embedding isn't rotation-invariant and a hand-held capture can be 90°/180° off)."""
    best = -1.0
    for k in range(4):
        candidate = image if k == 0 else np.rot90(image, k)
        vector = embed(candidate, model_path=model_path)
        best = max(best, float(vector @ reference.astype(np.float32)))
    return best


def assess_artwork_match(
    image_bytes: bytes, reference: np.ndarray | None, *, model_path: str
) -> AuthenticitySignal:
    """Compare the capture to a card's genuine reference embedding → an ``artwork_match`` signal."""
    if reference is None or not image_bytes:
        return _unreadable()
    try:
        rect = rectify_card(image_bytes)
        cosine = _best_oriented_cosine(rect.image, reference, model_path)
    except EmbeddingModelUnavailable:
        return _unreadable()
    except Exception:  # noqa: BLE001 - a bad capture must degrade to "couldn't compare", not error
        return _unreadable()

    if cosine >= _CONSISTENT_COSINE:
        # Scale confidence by the margin above the bar (0.78→floor, ~1.0→ceil).
        span = max(1e-6, 1.0 - _CONSISTENT_COSINE)
        conf = _CONF_FLOOR + (_CONF_CEIL - _CONF_FLOOR) * min(1.0, (cosine - _CONSISTENT_COSINE) / span)
        return AuthenticitySignal(
            kind=SignalKind.ARTWORK_MATCH,
            observation=SignalObservation.CONSISTENT,
            confidence=round(conf, 4),
            detail=SignalDetail.ARTWORK_MATCHES_REFERENCE,
        )
    return _unreadable()


def _unreadable() -> AuthenticitySignal:
    return AuthenticitySignal(
        kind=SignalKind.ARTWORK_MATCH,
        observation=SignalObservation.UNREADABLE,
        confidence=0.2,
        detail=SignalDetail.ARTWORK_NOT_COMPARED,
    )
