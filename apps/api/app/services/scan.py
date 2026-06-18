"""Scan orchestration: capture bundle → recognition → pricing → persisted response.

This owns the one product rule that can't live in a provider: when the top recognition
candidate is below the confirm threshold, return the top-2 with their € delta for the user
to choose rather than committing a guess (ADR 0002).

It also persists each scan as a ``ScanRecord`` against the calling user — the user's history
and, only with explicit consent, the raw material of the training moat. ``training_consent``
is never set here unless the caller passes it through from an explicit opt-in; the default is
off (charter §3.5, GDPR). A resolved scan also lands its card in the shared catalog so it is
immediately addable to the collection.

The consent moat is closed here: after a scan is recorded, it is offered to the data lake
through ``emit_scan``, whose gate emits *only* a consented, never-revoked record. A
not-consented scan is recorded as the user's history but never reaches the sink — the
privacy hard line is one gate, not a check scattered per call site.

Recognition+pricing is split out of persistence as ``classify`` so the batch/stack path
(``app.services.batch_scan``) reuses the exact same identify-and-price logic without
duplicating it — only the persistence/response shaping differs between single and batch.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal

from app.core.errors import PriceUnavailableError, RecognitionFailedError
from app.datalake.base import DataLakeSink
from app.datalake.emit import emit_scan
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


@dataclass(frozen=True, slots=True)
class ScanClassification:
    """The recognition+pricing verdict for one capture, before any persistence.

    This is the shared output of the identify-and-price path: the single-scan endpoint turns
    it into a ``ScanResponse`` and the batch endpoint folds it into a deduped per-item result.
    ``outcome`` is the terminal state; the other fields are populated per outcome:

    - ``resolved`` → ``card`` (identity + price), ``dedupe_key`` = the top candidate's canonical id.
    - ``needs_confirmation`` → ``choices`` (top-2) + ``price_delta``, ``dedupe_key`` = the top
      candidate's canonical id.
    - ``unrecognized`` → nothing priced; ``dedupe_key`` is ``None`` (no identity to collapse on).

    ``dedupe_key`` keys on the top candidate's canonical id alone — **not** the outcome — so two
    captures of one physical card whose confidence straddles the confirm threshold (resolved on
    one flip, needs_confirmation on the next) still collapse onto the same card in a stack.

    ``ranked`` is the candidate audit/training trail persisted on the ``ScanRecord``.
    """

    outcome: PersistedScanOutcome
    ranked: list[dict[str, object]]
    card: ScannedCard | None = None
    choices: list[ConfirmationChoice] | None = None
    price_delta: Decimal | None = None
    top_confidence: float | None = None
    dedupe_key: str | None = None


class ScanService:
    def __init__(
        self,
        *,
        recognition: RecognitionProvider,
        pricing: PricingProvider,
        data_lake: DataLakeSink,
        confirm_threshold: float,
    ) -> None:
        self._recognition = recognition
        self._pricing = pricing
        self._data_lake = data_lake
        self._confirm_threshold = confirm_threshold

    async def classify(self, bundle: CaptureBundleRef) -> ScanClassification:
        """Recognize and price one capture — no persistence, no quota, no side effects.

        The single source of truth for "what is this card and what's it worth", reused by both
        the single-scan and batch paths. The confirm rule (top-1 below threshold → surface the
        top-2 with their delta) lives here so neither caller can drift from it.
        """
        result = await self._recognition.recognize(bundle)
        if not result.candidates:
            return ScanClassification(
                outcome=PersistedScanOutcome.UNRECOGNIZED, ranked=[]
            )

        ranked = [_candidate_label(c) for c in result.candidates]

        if result.needs_confirmation(self._confirm_threshold):
            choices = await self._confirmation_choices(result.candidates[:2])
            return ScanClassification(
                outcome=PersistedScanOutcome.NEEDS_CONFIRMATION,
                ranked=ranked,
                choices=choices,
                price_delta=_price_delta(choices),
                top_confidence=result.top.confidence,
                dedupe_key=result.top.identity.canonical_id,
            )

        top = result.top
        return ScanClassification(
            outcome=PersistedScanOutcome.RESOLVED,
            ranked=ranked,
            card=ScannedCard(
                identity=top.identity,
                confidence=top.confidence,
                price=await self._price_or_none(top.identity.canonical_id),
            ),
            top_confidence=top.confidence,
            dedupe_key=top.identity.canonical_id,
        )

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
        verdict = await self.classify(bundle)

        if verdict.outcome is PersistedScanOutcome.UNRECOGNIZED:
            unrecognized = await scans.record(
                user_id=user_id,
                capture_ref=bundle.bundle_id,
                outcome=PersistedScanOutcome.UNRECOGNIZED,
                candidates=[],
                training_consent=training_consent,
                consent_note=consent_note,
            )
            await emit_scan(self._data_lake, unrecognized)
            raise RecognitionFailedError(
                "No card could be recognized in this capture.",
                details={"bundle_id": bundle.bundle_id},
            )

        if verdict.outcome is PersistedScanOutcome.NEEDS_CONFIRMATION:
            unconfirmed = await scans.record(
                user_id=user_id,
                capture_ref=bundle.bundle_id,
                outcome=PersistedScanOutcome.NEEDS_CONFIRMATION,
                candidates=verdict.ranked,
                top_confidence=verdict.top_confidence,
                training_consent=training_consent,
                consent_note=consent_note,
            )
            await emit_scan(self._data_lake, unconfirmed)
            return ScanResponse(
                outcome=ScanOutcome.NEEDS_CONFIRMATION,
                choices=verdict.choices,
                price_delta=verdict.price_delta,
            )

        # Resolved: land the identity in the shared catalog so it can be added to a collection
        # straight from this scan, then point the scan record at that row.
        assert verdict.card is not None  # resolved always carries a card
        card = await _upsert_card(cards, verdict.card.identity)
        resolved = await scans.record(
            user_id=user_id,
            capture_ref=bundle.bundle_id,
            outcome=PersistedScanOutcome.RESOLVED,
            candidates=verdict.ranked,
            top_confidence=verdict.top_confidence,
            resolved_card_id=card.id,
            training_consent=training_consent,
            consent_note=consent_note,
        )
        await emit_scan(self._data_lake, resolved)
        return ScanResponse(outcome=ScanOutcome.RESOLVED, card=verdict.card)

    async def _confirmation_choices(
        self, top_two: list[RecognitionCandidate]
    ) -> list[ConfirmationChoice]:
        return [
            ConfirmationChoice(
                identity=candidate.identity,
                confidence=candidate.confidence,
                price=await self._price_or_none(candidate.identity.canonical_id),
            )
            for candidate in top_two
        ]

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
