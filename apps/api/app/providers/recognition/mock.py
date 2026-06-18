"""Deterministic mock recognizer.

Stands in for Ximilar / the on-device detector until those land behind the same Protocol.
It maps a capture bundle to a fixed result by ``bundle_id`` so the whole scan flow — and
its tests — are reproducible without any model or network.

Two fixtures matter for exercising the product's branches:
- a high-confidence single (the common case that commits straight through), and
- a low-confidence top-2 where two same-art reprints differ ~30× in price, which is
  exactly the case that must route to user confirmation (ADR 0002).
The default for unknown bundles is the low-confidence case, so the harder path is what a
caller hits unless they opt into the easy one.
"""

from __future__ import annotations

from app.providers.base import CaptureBundle
from app.schemas.cards import (
    CardIdentity,
    RecognitionCandidate,
    RecognitionResult,
    Variant,
)

_CHARIZARD_BASE = CardIdentity(
    canonical_id="base1-4",
    name="Charizard",
    set_name="Base Set",
    collector_number="4/102",
    language="en",
    variant=Variant.HOLO,
)

_CHARIZARD_BASE2 = CardIdentity(
    canonical_id="base2-4",
    name="Charizard",
    set_name="Base Set 2",
    collector_number="4/130",
    language="en",
    variant=Variant.HOLO,
)

_BLASTOISE_BASE = CardIdentity(
    canonical_id="base1-2",
    name="Blastoise",
    set_name="Base Set",
    collector_number="2/102",
    language="en",
    variant=Variant.HOLO,
)

# bundle_id → ordered candidates. The first entry is the deterministic default.
_FIXTURES: dict[str, list[RecognitionCandidate]] = {
    "mock-high-confidence": [
        RecognitionCandidate(identity=_BLASTOISE_BASE, confidence=0.97),
    ],
    "mock-low-confidence": [
        RecognitionCandidate(identity=_CHARIZARD_BASE, confidence=0.61),
        RecognitionCandidate(identity=_CHARIZARD_BASE2, confidence=0.55),
    ],
}

_DEFAULT_BUNDLE = "mock-low-confidence"


class MockRecognitionProvider:
    """Returns a fixed ``RecognitionResult`` keyed on ``bundle.bundle_id``."""

    async def recognize(self, bundle: CaptureBundle) -> RecognitionResult:
        candidates = _FIXTURES.get(bundle.bundle_id) or _FIXTURES[_DEFAULT_BUNDLE]
        return RecognitionResult(candidates=list(candidates))
