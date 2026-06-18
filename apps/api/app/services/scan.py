"""Scan orchestration: capture bundle → recognition → pricing → persisted response.

This owns the one product rule that can't live in a provider: when the top recognition
candidate is below the confirm threshold, return the top-2 with their € delta for the user
to choose rather than committing a guess (ADR 0002).

It also persists each scan as a ``ScanRecord`` against the calling user — the user's history
and, only with explicit consent, the raw material of the training moat. ``training_consent``
is never set here unless the caller passes it through from an explicit opt-in; the default is
off (charter §3.5, GDPR). A resolved scan also lands its card in the shared catalog so it is
immediately addable to the collection.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from app.core.errors import PriceUnavailableError, RecognitionFailedError
from app.db.models.enums import ScanOutcome as PersistedScanOutcome
from app.db.models.enums import Variant as PersistedVariant
from app.db.repositories import CardRepository, ScanRepository
from app.providers.base import PricingProvider, RecognitionProvider
from app.schemas.cards import CardIdentity, PriceQuote, RecognitionCandidate
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

    async def scan(
        self,
        bundle: CaptureBundleRef,
        *,
        user_id: uuid.UUID,
        scans: ScanRepository,
        cards: CardRepository,
        training_consent: bool = False,
        consent_note: str | None = None,
    ) -> ScanResponse:
        result = await self._recognition.recognize(bundle)
        if not result.candidates:
            await scans.record(
                user_id=user_id,
                capture_ref=bundle.bundle_id,
                outcome=PersistedScanOutcome.UNRECOGNIZED,
                candidates=[],
                training_consent=training_consent,
                consent_note=consent_note,
            )
            raise RecognitionFailedError(
                "No card could be recognized in this capture.",
                details={"bundle_id": bundle.bundle_id},
            )

        ranked = [_candidate_label(c) for c in result.candidates]

        if result.needs_confirmation(self._confirm_threshold):
            response = await self._confirmation_response(result.candidates[:2])
            await scans.record(
                user_id=user_id,
                capture_ref=bundle.bundle_id,
                outcome=PersistedScanOutcome.NEEDS_CONFIRMATION,
                candidates=ranked,
                top_confidence=result.top.confidence,
                training_consent=training_consent,
                consent_note=consent_note,
            )
            return response

        top = result.top
        # Land the resolved identity in the shared catalog so it can be added to a
        # collection straight from this scan, then point the scan record at that row.
        card = await _upsert_card(cards, top.identity)
        response = ScanResponse(
            outcome=ScanOutcome.RESOLVED,
            card=ScannedCard(
                identity=top.identity,
                confidence=top.confidence,
                price=await self._price_or_none(top.identity.canonical_id),
            ),
        )
        await scans.record(
            user_id=user_id,
            capture_ref=bundle.bundle_id,
            outcome=PersistedScanOutcome.RESOLVED,
            candidates=ranked,
            top_confidence=top.confidence,
            resolved_card_id=card.id,
            training_consent=training_consent,
            consent_note=consent_note,
        )
        return response

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


async def _upsert_card(cards: CardRepository, identity: CardIdentity):
    """Persist the recognized identity into the catalog, idempotent on its canonical id.

    Recognition emits the same set/number/variant tuple the catalog keys on, so a re-scan of
    the same card resolves to one row. ``set_code`` is derived from the canonical id's set
    prefix (e.g. ``origins-12`` → ``origins``) until the nightly reference sync owns the catalog.
    """
    set_code = identity.canonical_id.rsplit("-", 1)[0]
    return await cards.upsert(
        canonical_id=identity.canonical_id,
        name=identity.name,
        set_name=identity.set_name,
        set_code=set_code,
        collector_number=identity.collector_number,
        language=identity.language,
        variant=PersistedVariant(identity.variant.value),
    )


def _candidate_label(candidate: RecognitionCandidate) -> dict[str, object]:
    """The JSON shape stored per hypothesis — a training label and a misfire audit trail."""
    return {
        "canonical_id": candidate.identity.canonical_id,
        "confidence": candidate.confidence,
    }


def _price_delta(choices: list[ConfirmationChoice]) -> Decimal | None:
    """The absolute € gap between the two priced choices, when both are priced."""
    if len(choices) < 2:
        return None
    a, b = choices[0].price, choices[1].price
    if a is None or b is None or a.value is None or b.value is None:
        return None
    return abs(a.value - b.value)
