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
    SignalKind,
    SignalObservation,
)

_Read = tuple[SignalObservation, float, str]

# capture_ref → per-signal (observation, confidence, detail) for the four *visual* signals.
_FIXTURES: dict[str, dict[SignalKind, _Read]] = {
    "capture-authentic": {
        SignalKind.PRINT_PATTERN: (
            SignalObservation.CONSISTENT,
            0.93,
            "CMYK rosette spacing and dot gain match the reference print run.",
        ),
        SignalKind.HOLO_SIGNATURE: (
            SignalObservation.CONSISTENT,
            0.90,
            "Foil reflectance shifts across the captured tilt angles as expected.",
        ),
        SignalKind.FONT_LAYOUT: (
            SignalObservation.CONSISTENT,
            0.95,
            "Typography weight, kerning and element placement match the reference layout.",
        ),
        SignalKind.CARDSTOCK: (
            SignalObservation.CONSISTENT,
            0.88,
            "Edge cross-section and surface texture are consistent with genuine stock.",
        ),
    },
    "capture-mixed": {
        SignalKind.PRINT_PATTERN: (
            SignalObservation.DEVIATION,
            0.86,
            "Dot pattern is coarser than the reference — characteristic of a rescreened print.",
        ),
        SignalKind.HOLO_SIGNATURE: (
            SignalObservation.CONSISTENT,
            0.84,
            "Foil behaviour across angles is within the genuine range.",
        ),
        SignalKind.FONT_LAYOUT: (
            SignalObservation.INCONCLUSIVE,
            0.70,
            "Typography is close to reference; minor differences fall within capture tolerance.",
        ),
        SignalKind.CARDSTOCK: (
            SignalObservation.DEVIATION,
            0.82,
            "Edge whitening and texture diverge from the reference stock.",
        ),
    },
    "capture-poor": {
        SignalKind.PRINT_PATTERN: (
            SignalObservation.UNREADABLE,
            0.22,
            "Capture lacks the magnification to resolve the dot pattern.",
        ),
        SignalKind.HOLO_SIGNATURE: (
            SignalObservation.UNREADABLE,
            0.18,
            "Only one angle captured — foil behaviour can't be read.",
        ),
        SignalKind.FONT_LAYOUT: (
            SignalObservation.INCONCLUSIVE,
            0.30,
            "Glare obscures part of the text; layout can't be compared confidently.",
        ),
        SignalKind.CARDSTOCK: (
            SignalObservation.UNREADABLE,
            0.20,
            "Edges are out of frame — stock and texture can't be assessed.",
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
