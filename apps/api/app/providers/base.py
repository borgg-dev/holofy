"""Swappable provider interfaces.

The buy-first/build-later strategy (architecture §3) hinges on every external capability
sitting behind a narrow Protocol so a mock, a bought API, or a future in-house model are
interchangeable at the call site. These Protocols are the seam:

- ``RecognitionProvider`` turns a capture bundle into ranked card identities.
- ``PricingProvider`` turns a canonical card id into a € quote.
- ``GradingProvider`` turns a capture into the *bought* PSA sub-scores — corners, edges,
  surface. Centering is built in-house (``app.grading.centering``) and never goes through
  this seam: it is a direct measurement we can audit, not a rented model output (§3.2).
- ``AuthenticityProvider`` turns a capture into the per-signal authenticity reads
  (print-pattern, holo, font/layout, cardstock). The catalog-existence cross-check is *not*
  here: it is a deterministic reference-DB lookup the service owns, not a model output.

Protocols (structural typing) rather than ABCs: providers need not inherit anything, and
the mock implementations stay trivially substitutable in tests.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.schemas.authenticity import AuthenticitySignal
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
    # The user's language preference (ISO code, e.g. "en"/"fr"), if the client sent one. Lets the
    # recognizer break an otherwise-unresolvable EN·FR same-name twin tie toward the user's market
    # — the picture can't, but their locale can. Optional: providers read it defensively (a missing
    # value ⇒ the honest confirm behaviour), so a bundle without it is still valid.
    preferred_language: str | None


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


class AuthenticityCapture(Protocol):
    """The minimum an authenticity model needs about a capture.

    ``image_count`` lets a provider reason about what it can read: the holo signature needs
    multiple tilt angles, so a single-frame capture caps what that signal can claim. As with
    the other captures, real ones reference stills in object storage rather than carrying
    bytes — the provider resolves them.
    """

    capture_ref: str
    image_count: int


@runtime_checkable
class AuthenticityProvider(Protocol):
    """Reads the per-signal authenticity cues for a capture (architecture §3.3).

    Returns one ``AuthenticitySignal`` per *visual* signal — print pattern, holo signature,
    font/layout, cardstock — each an observation band plus the provider's own confidence in
    that read. The catalog-existence cross-check is deliberately absent: it is a deterministic
    reference-DB lookup the service performs, not a rented/learned model output. The real
    provider (a CV ensemble) drops in behind this exact signature later (ADR 0006), so the
    service never knows whether a read was bought, built, or mocked — and never receives, or
    emits, a binary fake/genuine verdict (charter §3.5).
    """

    async def analyze(self, capture: AuthenticityCapture) -> list[AuthenticitySignal]: ...
