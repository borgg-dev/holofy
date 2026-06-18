"""Swappable provider interfaces.

The buy-first/build-later strategy (architecture §3) hinges on every external capability
sitting behind a narrow Protocol so a mock, a bought API, or a future in-house model are
interchangeable at the call site. These two Protocols are the seam:

- ``RecognitionProvider`` turns a capture bundle into ranked card identities.
- ``PricingProvider`` turns a canonical card id into a € quote.

Protocols (structural typing) rather than ABCs: providers need not inherit anything, and
the mock implementations stay trivially substitutable in tests.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.schemas.cards import PriceQuote, RecognitionResult


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
