"""Scan orchestration: capture bundle → recognition → pricing → response DTO.

This is the contract stub for the core scan loop (Phase 1). It owns the one product rule
that can't live in a provider: when the top recognition candidate is below the confirm
threshold, return the top-2 with their € delta for the user to choose, rather than
committing a guess. The real pipeline (P1.4) will add portfolio write + async grading
behind this same entry point; the provider seam keeps recognition and pricing swappable.
"""

from __future__ import annotations

from decimal import Decimal

from app.core.errors import PriceUnavailableError, RecognitionFailedError
from app.providers.base import PricingProvider, RecognitionProvider
from app.schemas.cards import PriceQuote, RecognitionCandidate
from app.schemas.scan import (
    CaptureBundleRef,
    ConfirmationChoice,
    ScanOutcome,
    ScannedCard,
    ScanResponse,
)


class ScanService:
    def __init__(
        self,
        *,
        recognition: RecognitionProvider,
        pricing: PricingProvider,
        confirm_threshold: float,
    ) -> None:
        self._recognition = recognition
        self._pricing = pricing
        self._confirm_threshold = confirm_threshold

    async def scan(self, bundle: CaptureBundleRef) -> ScanResponse:
        result = await self._recognition.recognize(bundle)
        if not result.candidates:
            raise RecognitionFailedError(
                "No card could be recognized in this capture.",
                details={"bundle_id": bundle.bundle_id},
            )

        if result.needs_confirmation(self._confirm_threshold):
            return await self._confirmation_response(result.candidates[:2])

        top = result.top
        return ScanResponse(
            outcome=ScanOutcome.RESOLVED,
            card=ScannedCard(
                identity=top.identity,
                confidence=top.confidence,
                price=await self._price_or_none(top.identity.canonical_id),
            ),
        )

    async def _confirmation_response(
        self, top_two: list[RecognitionCandidate]
    ) -> ScanResponse:
        choices = [
            ConfirmationChoice(
                identity=candidate.identity,
                confidence=candidate.confidence,
                price=await self._price_or_none(candidate.identity.canonical_id),
            )
            for candidate in top_two
        ]
        return ScanResponse(
            outcome=ScanOutcome.NEEDS_CONFIRMATION,
            choices=choices,
            price_delta=_price_delta(choices),
        )

    async def _price_or_none(self, canonical_id: str) -> PriceQuote | None:
        # A missing price is a long-tail fact, not a scan failure — the identity still
        # stands and the UI shows "no price yet". Other pricing faults propagate.
        try:
            return await self._pricing.price(canonical_id)
        except PriceUnavailableError:
            return None


def _price_delta(choices: list[ConfirmationChoice]) -> Decimal | None:
    """The absolute € gap between the two priced choices, when both are priced."""
    if len(choices) < 2:
        return None
    a, b = choices[0].price, choices[1].price
    if a is None or b is None or a.value is None or b.value is None:
        return None
    return abs(a.value - b.value)
