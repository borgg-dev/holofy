"""Stack/batch scan orchestration: many captures in, deduped per-card results out (P4.1).

The user flips through a stack; the client uploads a bundle per detected card. This service
identifies + prices each through the *same* ``ScanService.classify`` path the single scan
uses — **ID + value only**, no grade/auth (master plan §7) — under the same COGS discipline:

1. **Charge before recognizing — per capture, in submission order.** Recognition *is* the
   COGS unit (one Ximilar credit), so it is gated by quota *before* it happens, exactly as
   single ``/scan`` charges before it recognizes. Each capture atomically consumes one unit of
   the free tier's daily scan budget (master plan §4, the same ``scan:{user_id}`` key); a
   capture the day's budget can't cover is marked ``quota_exceeded`` and the recognizer is
   **never called** for it — no credit spent. Recognition calls are therefore bounded by the
   remaining daily budget, and ``MAX_BATCH_ITEMS`` caps the request on top.

2. **Dedupe by identity — for banking and display, not refunds.** Among the *recognized*
   captures, ones that read as the same physical card collapse into one result, keyed on the
   card's canonical id regardless of whether each read was ``resolved`` or ``needs_confirmation``
   (so a threshold-straddling re-flip still merges). ``count`` is how many captures merged.
   Quota was already spent per capture; dedupe never refunds it — it only stops one card from
   *banking* twice. Unrecognized captures never dedupe (no identity to collapse on); each stays
   its own item so the user can re-capture exactly the ones that missed.

Persistence mirrors the single path exactly: each *distinct accepted* card is recorded once as
a ``ScanRecord`` (consent stamped from the account, off by default) and offered to the data lake
through the same ``emit_scan`` gate — so a deduped stack writes one record and one consented
example per card, never one per flip.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from app.datalake.base import DataLakeSink
from app.datalake.emit import emit_scan
from app.db.models.enums import ScanOutcome as PersistedScanOutcome
from app.db.repositories import CardRepository, ScanRepository
from app.ratelimit.base import RateLimiter
from app.schemas.batch_scan import (
    BatchItemOutcome,
    BatchScanItem,
    BatchScanQuota,
    BatchScanResponse,
)
from app.schemas.scan import CaptureBundleRef
from app.services.scan import ScanClassification, ScanService, _upsert_card

# Maps the persisted outcome of an *accepted* (recognized) card to its API-facing batch outcome.
_BATCH_OUTCOME = {
    PersistedScanOutcome.RESOLVED: BatchItemOutcome.RESOLVED,
    PersistedScanOutcome.NEEDS_CONFIRMATION: BatchItemOutcome.NEEDS_CONFIRMATION,
}


@dataclass
class _Accumulator:
    """A deduped card under construction: its first verdict plus the flips that merged onto it."""

    verdict: ScanClassification
    capture_refs: list[str] = field(default_factory=list)


class BatchScanService:
    def __init__(
        self,
        *,
        scan_service: ScanService,
        data_lake: DataLakeSink,
        limiter: RateLimiter,
        quota_key: str,
        daily_limit: int,
    ) -> None:
        self._scan = scan_service
        self._data_lake = data_lake
        self._limiter = limiter
        self._quota_key = quota_key
        self._daily_limit = daily_limit

    async def scan_batch(
        self,
        items: list[CaptureBundleRef],
        *,
        user_id: uuid.UUID,
        scans: ScanRepository,
        cards: CardRepository,
        training_consent: bool = False,
        consent_note: str | None = None,
    ) -> BatchScanResponse:
        deduped: dict[str, _Accumulator] = {}
        unrecognized: list[CaptureBundleRef] = []
        exhausted: list[CaptureBundleRef] = []

        # Charge before recognizing, per capture, in submission order: recognition is the COGS
        # unit, so it must be gated by the daily budget *before* it runs (same as single /scan).
        # A capture the budget can't cover never reaches the recognizer — no credit is spent.
        charged = 0
        remaining = self._daily_limit
        for bundle in items:
            window = await self._limiter.check_and_consume(
                self._quota_key, limit=self._daily_limit
            )
            remaining = window.remaining
            if not window.allowed:
                exhausted.append(bundle)
                continue

            charged += 1
            verdict = await self._scan.classify(bundle)
            if verdict.dedupe_key is None:  # unrecognized — no identity to collapse on
                unrecognized.append(bundle)
                continue
            self._fold(deduped, verdict, bundle.bundle_id)

        # Bank one record per distinct recognized card; quota was already spent per capture, so
        # dedupe collapses banking and display only — it never refunds the units those flips cost.
        result_items: list[BatchScanItem] = []
        for acc in deduped.values():
            result_items.append(
                await self._persist_accepted(
                    acc,
                    user_id=user_id,
                    scans=scans,
                    cards=cards,
                    training_consent=training_consent,
                    consent_note=consent_note,
                )
            )

        for bundle in unrecognized:
            result_items.append(
                await self._persist_unrecognized(
                    bundle,
                    user_id=user_id,
                    scans=scans,
                    training_consent=training_consent,
                    consent_note=consent_note,
                )
            )

        if exhausted:
            # The captures that hit the daily wall: surfaced, never recognized, never banked.
            result_items.append(
                BatchScanItem(
                    outcome=BatchItemOutcome.QUOTA_EXCEEDED,
                    count=len(exhausted),
                    capture_refs=[bundle.bundle_id for bundle in exhausted],
                )
            )

        return BatchScanResponse(
            items=result_items,
            quota=BatchScanQuota(
                limit=self._daily_limit,
                charged=charged,
                remaining=max(remaining, 0),
                rejected=len(exhausted),
            ),
        )

    @staticmethod
    def _fold(
        deduped: dict[str, _Accumulator],
        verdict: ScanClassification,
        bundle_id: str,
    ) -> None:
        """Merge one recognized capture into its card's accumulator, keyed on canonical id.

        First read of a card seeds the verdict; later flips add their capture ref. A confident
        (``resolved``) read upgrades a card first seen as ``needs_confirmation`` so a
        threshold-straddling stack lands on the priced result rather than the confirm prompt.
        """
        acc = deduped.get(verdict.dedupe_key)
        if acc is None:
            deduped[verdict.dedupe_key] = _Accumulator(
                verdict=verdict, capture_refs=[bundle_id]
            )
            return
        acc.capture_refs.append(bundle_id)
        if (
            verdict.outcome is PersistedScanOutcome.RESOLVED
            and acc.verdict.outcome is not PersistedScanOutcome.RESOLVED
        ):
            acc.verdict = verdict

    async def _persist_accepted(
        self,
        acc: _Accumulator,
        *,
        user_id: uuid.UUID,
        scans: ScanRepository,
        cards: CardRepository,
        training_consent: bool,
        consent_note: str | None,
    ) -> BatchScanItem:
        verdict = acc.verdict
        resolved_card_id: uuid.UUID | None = None
        if verdict.outcome is PersistedScanOutcome.RESOLVED:
            assert verdict.card is not None  # resolved always carries a card
            resolved_card_id = (await _upsert_card(cards, verdict.card.identity)).id

        # One record per deduped card, capture_ref = the first flip that produced it (the rest
        # are merged quantity, not separate scan events).
        record = await scans.record(
            user_id=user_id,
            capture_ref=acc.capture_refs[0],
            outcome=verdict.outcome,
            candidates=verdict.ranked,
            top_confidence=verdict.top_confidence,
            resolved_card_id=resolved_card_id,
            training_consent=training_consent,
            consent_note=consent_note,
        )
        await emit_scan(self._data_lake, record)

        return BatchScanItem(
            outcome=_BATCH_OUTCOME[verdict.outcome],
            count=len(acc.capture_refs),
            capture_refs=acc.capture_refs,
            card=verdict.card,
            choices=verdict.choices,
            price_delta=verdict.price_delta,
        )

    async def _persist_unrecognized(
        self,
        bundle: CaptureBundleRef,
        *,
        user_id: uuid.UUID,
        scans: ScanRepository,
        training_consent: bool,
        consent_note: str | None,
    ) -> BatchScanItem:
        record = await scans.record(
            user_id=user_id,
            capture_ref=bundle.bundle_id,
            outcome=PersistedScanOutcome.UNRECOGNIZED,
            candidates=[],
            training_consent=training_consent,
            consent_note=consent_note,
        )
        await emit_scan(self._data_lake, record)
        return BatchScanItem(
            outcome=BatchItemOutcome.UNRECOGNIZED,
            count=1,
            capture_refs=[bundle.bundle_id],
        )
