"""Build training examples from persisted records, and the one consent gate they pass.

This is the seam between "a record was written" and "an example entered the lake". It exists
so the privacy hard line — *only* a consented, never-revoked record produces an example — is
expressed once, here, rather than re-checked at each of the three emission sites (scan,
pre-grade, authenticity). Each site calls ``emit_*``; the gate inside short-circuits a
non-consented or revoked record to a no-op before the sink is ever touched.

Where the async boundary goes: today these ``await sink.emit(...)`` calls run inline on the
request. When the real EU-region lake lands, the sink's ``emit`` becomes an enqueue (SQS /
Redis) and the actual lake write moves to a worker — the call site does not change, because
it already depends only on the ``DataLakeSink`` Protocol. The labels are lifted from the JSON
the record already stores, so the lake row and the audit trail can't drift.
"""

from __future__ import annotations

from app.datalake.base import DataLakeSink
from app.db.models.authenticity import AuthenticityRecord
from app.db.models.pregrade import PreGradeRecord
from app.db.models.scan import ScanRecord
from app.schemas.datalake import TrainingExample, TrainingExampleKind


def _is_consented(training_consent: bool, consent_revoked_at: object) -> bool:
    """The single definition of "eligible for the lake": opted in, never revoked.

    Mirrors the repositories' ``list_training_eligible`` predicate exactly, so the live
    emission gate and the batch ingest gate can never disagree about what consent means.
    """
    return bool(training_consent) and consent_revoked_at is None


async def emit_scan(sink: DataLakeSink, record: ScanRecord) -> bool:
    """Emit a scan as a training example iff it carries standing consent. Returns whether it did."""
    if not _is_consented(record.training_consent, record.consent_revoked_at):
        return False
    await sink.emit(
        TrainingExample(
            kind=TrainingExampleKind.SCAN,
            record_id=record.id,
            user_id=record.user_id,
            capture_ref=record.capture_ref,
            resolved_card_id=record.resolved_card_id,
            labels={
                "outcome": record.outcome,
                "candidates": record.candidates,
                "top_confidence": record.top_confidence,
            },
        )
    )
    return True


async def emit_pregrade(sink: DataLakeSink, record: PreGradeRecord) -> bool:
    """Emit a pre-grade as a training example iff it carries standing consent."""
    if not _is_consented(record.training_consent, record.consent_revoked_at):
        return False
    await sink.emit(
        TrainingExample(
            kind=TrainingExampleKind.PREGRADE,
            record_id=record.id,
            user_id=record.user_id,
            capture_ref=record.capture_ref,
            resolved_card_id=record.card_id,
            labels={
                "status": record.status,
                "likely_low": record.likely_low,
                "likely_high": record.likely_high,
                "at_least": record.at_least,
                "p_at_least": record.p_at_least,
                "confidence": record.confidence,
                "sub_scores": record.sub_scores,
            },
        )
    )
    return True


async def emit_authenticity(sink: DataLakeSink, record: AuthenticityRecord) -> bool:
    """Emit an authenticity screen as a training example iff it carries standing consent."""
    if not _is_consented(record.training_consent, record.consent_revoked_at):
        return False
    await sink.emit(
        TrainingExample(
            kind=TrainingExampleKind.AUTHENTICITY,
            record_id=record.id,
            user_id=record.user_id,
            capture_ref=record.capture_ref,
            resolved_card_id=record.card_id,
            labels={
                "status": record.status,
                "risk_band": record.risk_band,
                "confidence": record.confidence,
                "signals": record.signals,
            },
        )
    )
    return True
