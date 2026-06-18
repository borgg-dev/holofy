"""Swappable provider interfaces.

The buy-first/build-later strategy (architecture §3) hinges on every external capability
sitting behind a narrow Protocol so a mock, a bought API, or a future in-house model are
interchangeable at the call site. These Protocols are the seam:

- ``RecognitionProvider`` turns a capture bundle into ranked card identities.
- ``PricingProvider`` turns a canonical card id into a € quote.
- ``GradingProvider`` turns a capture into the *bought* PSA sub-scores — corners, edges,
  surface. Centering is built in-house (``app.grading.centering``) and never goes through
  this seam: it is a direct measurement we can audit, not a rented model output (§3.2).

Protocols (structural typing) rather than ABCs: providers need not inherit anything, and
the mock implementations stay trivially substitutable in tests.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.schemas.cards import PriceQuote, RecognitionResult
from app.schemas.grading import SubScore


class CaptureBundle(Protocol):
    """The minimum a recognizer needs about a capture.

    Real bundles reference uploaded stills in object storage rather than carrying bytes;
    the provider resolves the reference itself. Kept as a Protocol so the storage shape can
    evolve without touching provider signatures.
    """

    bundle_id: str
    image_count: int


@runtime_checkable
class RecognitionProvider(Protocol):
    async def recognize(self, bundle: CaptureBundle) -> RecognitionResult: ...


@runtime_checkable
class PricingProvider(Protocol):
    async def price(self, canonical_id: str) -> PriceQuote: ...


class GradingCapture(Protocol):
    """The minimum a grading model needs about a capture.

    ``image_count`` lets a provider reason about what it can actually score: surface and
    holo defects need multiple angles, so a single-frame capture caps what corners/edges/
    surface can claim. As with ``CaptureBundle``, real captures reference stills in object
    storage rather than carrying bytes.
    """

    capture_ref: str
    image_count: int


@runtime_checkable
class GradingProvider(Protocol):
    """Scores the three *bought* PSA sub-grades for a capture.

    Returns one ``SubScore`` per axis in ``corners``, ``edges``, ``surface`` — each a score
    plus the provider's own confidence in that read. Centering is deliberately absent: it is
    measured in-house. The real provider (Ximilar ``/v2/grade``) drops in behind this exact
    signature later (ADR-tracked), so the service never knows whether a score was bought or
    built.
    """

    async def grade(self, capture: GradingCapture) -> list[SubScore]: ...
