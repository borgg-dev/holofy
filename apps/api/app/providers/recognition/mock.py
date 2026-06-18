"""Deterministic mock recognizer.

Stands in for Ximilar / the on-device detector until those land behind the same Protocol.
It maps a capture bundle to a fixed result by ``bundle_id`` so the whole scan flow — and
its tests — are reproducible without any model or network.

The fixtures exercise the product's branches:
- a high-confidence single (the common case that commits straight through),
- a second high-confidence single (a distinct card, so a stack scan has more than one to
  dedupe and resolve), a low-confidence top-2 where two same-art reprints differ ~30× in
  price — the case that must route to user confirmation (ADR 0002), and
- an empty result (``mock-unrecognized``) for the no-card-read branch the stack surfaces
  per item.
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

# Holofy's own fixtures use invented cards — original creatures and sets, not real
# trademarks — so nothing we ship carries someone else's IP. The Emberwyrm Sovereign
# pair is the load-bearing one: same creature and art, two printings ~31× apart in price.
_EMBERWYRM_ORIGINS = CardIdentity(
    canonical_id="origins-12",
    name="Emberwyrm Sovereign",
    set_name="Origins Vault",
    collector_number="12/120",
    language="en",
    variant=Variant.HOLO,
)

_EMBERWYRM_ECHO = CardIdentity(
    canonical_id="echo-12",
    name="Emberwyrm Sovereign",
    set_name="Echo Reprint",
    collector_number="12/95",
    language="en",
    variant=Variant.HOLO,
)

_TIDECALLER_ORIGINS = CardIdentity(
    canonical_id="origins-8",
    name="Tidecaller Leviath",
    set_name="Origins Vault",
    collector_number="8/120",
    language="en",
    variant=Variant.HOLO,
)

_EMBERWYRM_ORIGINS_RESOLVED = CardIdentity(
    canonical_id="origins-12",
    name="Emberwyrm Sovereign",
    set_name="Origins Vault",
    collector_number="12/120",
    language="en",
    variant=Variant.HOLO,
)

# bundle_id → ordered candidates. The first entry is the deterministic default.
_FIXTURES: dict[str, list[RecognitionCandidate]] = {
    "mock-high-confidence": [
        RecognitionCandidate(identity=_TIDECALLER_ORIGINS, confidence=0.97),
    ],
    # A second confident single, a different card — so a stack has two distinct resolves to
    # dedupe across rather than collapsing everything onto one fixture.
    "mock-high-confidence-2": [
        RecognitionCandidate(identity=_EMBERWYRM_ORIGINS_RESOLVED, confidence=0.95),
    ],
    "mock-low-confidence": [
        RecognitionCandidate(identity=_EMBERWYRM_ORIGINS, confidence=0.61),
        RecognitionCandidate(identity=_EMBERWYRM_ECHO, confidence=0.55),
    ],
    # No card could be read — the per-item "re-capture this one" branch of a stack.
    "mock-unrecognized": [],
}

_DEFAULT_BUNDLE = "mock-low-confidence"


class MockRecognitionProvider:
    """Returns a fixed ``RecognitionResult`` keyed on ``bundle.bundle_id``."""

    async def recognize(self, bundle: CaptureBundle) -> RecognitionResult:
        # A known bundle uses its fixture as-is (including a deliberately empty one for the
        # unrecognized branch); only a truly unknown bundle falls back to the default.
        if bundle.bundle_id in _FIXTURES:
            candidates = _FIXTURES[bundle.bundle_id]
        else:
            candidates = _FIXTURES[_DEFAULT_BUNDLE]
        return RecognitionResult(candidates=list(candidates))
