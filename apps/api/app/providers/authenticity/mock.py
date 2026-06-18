"""Deterministic mock authenticity analyzer for the four visual signals.

Stands in for the eventual CV ensemble (print-pattern / rosette, holo signature, font/layout,
cardstock) until it lands behind the same ``AuthenticityProvider`` Protocol. It maps a
capture to fixed per-signal reads keyed on ``capture_ref`` so the whole assessment flow — and
its tests — are reproducible with no model and no network.

The fixtures exercise the composition's branches honestly:

- ``capture-authentic`` — every visual signal consistent and confidently read: the case that
  composes to the most reassuring band the service will emit (``strong_signals``), but still
  not a "genuine" verdict.
- ``capture-mixed`` — a real-world ambiguity: print pattern and cardstock deviate while the
  rest read consistent, all at solid confidence. The composite must land ``inconclusive`` /
  ``elevated_risk`` from the *evidence*, never assert a fake.
- ``capture-poor`` (the default for unknown refs) — a capture the model could barely read:
  signals come back ``unreadable`` at low confidence, so the composite must refuse with a
  retake signal rather than emit a confident wrong band.

Note the deliberate absence of a ``catalog_existence`` signal: that cross-check is the
service's deterministic reference-DB lookup, not a model output, so it never originates here.
"""

from __future__ import annotations

from app.providers.base import AuthenticityCapture
from app.schemas.authenticity import (
    AuthenticitySignal,
    SignalDetail,
    SignalKind,
    SignalObservation,
)

_Read = tuple[SignalObservation, float, SignalDetail]

# capture_ref → per-signal (observation, confidence, detail) for the four *visual* signals.
_FIXTURES: dict[str, dict[SignalKind, _Read]] = {
    "capture-authentic": {
        SignalKind.PRINT_PATTERN: (
            SignalObservation.CONSISTENT,
            0.93,
            SignalDetail.PRINT_MATCHES_REFERENCE,
        ),
        SignalKind.HOLO_SIGNATURE: (
            SignalObservation.CONSISTENT,
            0.90,
            SignalDetail.HOLO_MATCHES_REFERENCE,
        ),
        SignalKind.FONT_LAYOUT: (
            SignalObservation.CONSISTENT,
            0.95,
            SignalDetail.LAYOUT_MATCHES_REFERENCE,
        ),
        SignalKind.CARDSTOCK: (
            SignalObservation.CONSISTENT,
            0.88,
            SignalDetail.STOCK_MATCHES_REFERENCE,
        ),
    },
    "capture-mixed": {
        SignalKind.PRINT_PATTERN: (
            SignalObservation.DEVIATION,
            0.86,
            SignalDetail.PRINT_DIFFERS_FROM_REFERENCE,
        ),
        SignalKind.HOLO_SIGNATURE: (
            SignalObservation.CONSISTENT,
            0.84,
            SignalDetail.HOLO_MATCHES_REFERENCE,
        ),
        SignalKind.FONT_LAYOUT: (
            SignalObservation.INCONCLUSIVE,
            0.70,
            SignalDetail.LAYOUT_WITHIN_TOLERANCE,
        ),
        SignalKind.CARDSTOCK: (
            SignalObservation.DEVIATION,
            0.82,
            SignalDetail.STOCK_DIFFERS_FROM_REFERENCE,
        ),
    },
    "capture-poor": {
        SignalKind.PRINT_PATTERN: (
            SignalObservation.UNREADABLE,
            0.22,
            SignalDetail.PRINT_TOO_COARSE_TO_READ,
        ),
        SignalKind.HOLO_SIGNATURE: (
            SignalObservation.UNREADABLE,
            0.18,
            SignalDetail.HOLO_NEEDS_MORE_ANGLES,
        ),
        SignalKind.FONT_LAYOUT: (
            SignalObservation.INCONCLUSIVE,
            0.30,
            SignalDetail.LAYOUT_OBSCURED,
        ),
        SignalKind.CARDSTOCK: (
            SignalObservation.UNREADABLE,
            0.20,
            SignalDetail.STOCK_OUT_OF_FRAME,
        ),
    },
}

# Unknown captures get the poor case, so a caller hits the harder path — the one that must
# refuse on poor capture — unless they opt into an easy one.
_DEFAULT_CAPTURE = "capture-poor"


class MockAuthenticityProvider:
    """Returns fixed per-signal ``AuthenticitySignal``s keyed on ``capture.capture_ref``."""

    async def analyze(self, capture: AuthenticityCapture) -> list[AuthenticitySignal]:
        reads = _FIXTURES.get(capture.capture_ref) or _FIXTURES[_DEFAULT_CAPTURE]
        return [
            AuthenticitySignal(
                kind=kind, observation=observation, confidence=confidence, detail=detail
            )
            for kind, (observation, confidence, detail) in reads.items()
        ]
