"""The consent moat, proven end to end: only consented captures reach the data lake.

This is the privacy hard line (charter §3.5, architecture §6). The tests deliberately try to
*falsify* it — a non-consented record, and a revoked one, must each produce ZERO training
examples — alongside confirming a consented record produces exactly one. The scan path is
exercised through the real ``ScanService``; the pre-grade and authenticity paths through the
shared ``emit_*`` gate the endpoints call, against real persisted records.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.datalake.emit import emit_authenticity, emit_pregrade, emit_scan
from app.datalake.mock import MockDataLakeSink
from app.db.models.enums import PregradeStatus, ScanOutcome
from app.db.repositories import (
    AuthenticityRepository,
    CardRepository,
    PreGradeRepository,
    ScanRepository,
    UserRepository,
)
from app.providers.pricing.mock import MockPricingProvider
from app.schemas.cards import (
    CardIdentity,
    RecognitionCandidate,
    RecognitionResult,
    Variant,
)
from app.schemas.datalake import TrainingExampleKind
from app.schemas.scan import CaptureBundleRef
from app.services.scan import ScanService

_THRESHOLD = 0.85


def _identity(canonical_id: str) -> CardIdentity:
    return CardIdentity(
        canonical_id=canonical_id,
        name="Tidecaller Leviath",
        set_name="Origins Vault",
        collector_number="8/120",
        language="en",
        variant=Variant.HOLO,
    )


class _StubRecognition:
    def __init__(self, result: RecognitionResult) -> None:
        self._result = result

    async def recognize(self, _bundle) -> RecognitionResult:  # noqa: ANN001
        return self._result


def _scan_service(sink: MockDataLakeSink) -> ScanService:
    # A confident single candidate so the scan resolves and records straight through.
    result = RecognitionResult(
        candidates=[RecognitionCandidate(identity=_identity("origins-8"), confidence=0.97)]
    )
    return ScanService(
        recognition=_StubRecognition(result),
        pricing=MockPricingProvider(),
        data_lake=sink,
        confirm_threshold=_THRESHOLD,
    )


async def _scan(
    service: ScanService, session: AsyncSession, *, training_consent: bool
):
    user = await UserRepository(session).create()
    await service.scan(
        CaptureBundleRef(bundle_id="b", training_consent=training_consent),
        user_id=user.id,
        scans=ScanRepository(session),
        cards=CardRepository(session),
        training_consent=training_consent,
    )
    return user


@pytest.mark.asyncio
async def test_consented_scan_emits_exactly_one_training_example(
    session: AsyncSession,
) -> None:
    sink = MockDataLakeSink()
    await _scan(_scan_service(sink), session, training_consent=True)

    examples = sink.examples_of(TrainingExampleKind.SCAN)
    assert len(examples) == 1
    example = examples[0]
    assert example.kind is TrainingExampleKind.SCAN
    assert example.capture_ref == "b"
    assert example.resolved_card_id is not None
    # The label carries the recognition outcome the model trains against.
    assert example.labels["outcome"] == ScanOutcome.RESOLVED


@pytest.mark.asyncio
async def test_non_consented_scan_emits_zero_examples(session: AsyncSession) -> None:
    # The privacy hard line: a default (consent-off) scan is the user's history and nothing
    # more. Nothing must reach the lake.
    sink = MockDataLakeSink()
    user = await _scan(_scan_service(sink), session, training_consent=False)

    assert sink.examples == []
    # ...and the scan *was* recorded — it is history, just not training-eligible.
    records = await ScanRepository(session).list_for_user(user.id)
    assert len(records) == 1
    assert records[0].training_consent is False


@pytest.mark.asyncio
async def test_revoked_consent_record_never_emits(session: AsyncSession) -> None:
    # A record whose consent was withdrawn must never produce a lake example, even though the
    # row still exists in history. We re-run the gate against the revoked record directly.
    sink = MockDataLakeSink()
    repo = ScanRepository(session)
    user = await UserRepository(session).create()
    scan = await repo.record(
        user_id=user.id,
        capture_ref="b",
        outcome=ScanOutcome.RESOLVED,
        training_consent=True,
    )
    await repo.revoke_training_consent(scan)

    emitted = await emit_scan(sink, scan)
    assert emitted is False
    assert sink.examples == []


@pytest.mark.asyncio
async def test_consented_pregrade_emits_one_and_non_consented_emits_zero(
    session: AsyncSession,
) -> None:
    sink = MockDataLakeSink()
    repo = PreGradeRepository(session)
    user = await UserRepository(session).create()

    from app.schemas.grading import (
        GradeProbabilityRange,
        GradingAxis,
        PregradeResponse,
        SubScore,
    )

    response = PregradeResponse(
        status=PregradeStatus.ESTIMATED,
        probability=GradeProbabilityRange(
            likely_low=8, likely_high=9, at_least=8, p_at_least=0.7
        ),
        sub_scores=[SubScore(axis=GradingAxis.CENTERING, score=9.0, confidence=0.9)],
        confidence=0.9,
    )

    consented = await repo.record(
        response, user_id=user.id, capture_ref="pg-1", training_consent=True
    )
    not_consented = await repo.record(
        response, user_id=user.id, capture_ref="pg-2", training_consent=False
    )

    assert await emit_pregrade(sink, consented) is True
    assert await emit_pregrade(sink, not_consented) is False

    examples = sink.examples_of(TrainingExampleKind.PREGRADE)
    assert len(examples) == 1
    assert examples[0].capture_ref == "pg-1"
    assert examples[0].labels["status"] == PregradeStatus.ESTIMATED


@pytest.mark.asyncio
async def test_consented_authenticity_emits_one_and_non_consented_emits_zero(
    session: AsyncSession,
) -> None:
    sink = MockDataLakeSink()
    repo = AuthenticityRepository(session)
    user = await UserRepository(session).create()

    from app.schemas.authenticity import (
        AuthenticityAssessment,
        AuthenticityResponse,
        AuthenticitySignal,
        AuthenticityStatus as ApiAuthStatus,
        RiskBand,
        SignalDetail,
        SignalKind,
        SignalObservation,
    )

    response = AuthenticityResponse(
        status=ApiAuthStatus.ASSESSED,
        assessment=AuthenticityAssessment(
            risk_band=RiskBand.STRONG_SIGNALS,
            confidence=0.8,
            signals=[
                AuthenticitySignal(
                    kind=SignalKind.PRINT_PATTERN,
                    observation=SignalObservation.CONSISTENT,
                    confidence=0.8,
                    detail=SignalDetail.PRINT_MATCHES_REFERENCE,
                )
            ],
            recommend_authentication=False,
            reference_value_eur=757.10,
        ),
    )

    consented = await repo.record(
        response, user_id=user.id, capture_ref="auth-1", training_consent=True
    )
    not_consented = await repo.record(
        response, user_id=user.id, capture_ref="auth-2", training_consent=False
    )

    assert await emit_authenticity(sink, consented) is True
    assert await emit_authenticity(sink, not_consented) is False

    examples = sink.examples_of(TrainingExampleKind.AUTHENTICITY)
    assert len(examples) == 1
    assert examples[0].capture_ref == "auth-1"
    # The label carries the risk band (a three-band value, never a fake/genuine boolean).
    assert examples[0].labels["risk_band"] == RiskBand.STRONG_SIGNALS


@pytest.mark.asyncio
async def test_sink_is_idempotent_on_kind_and_record_id(session: AsyncSession) -> None:
    # A retried request must not double-count: re-emitting the same record updates its one
    # example in place rather than appending a duplicate.
    sink = MockDataLakeSink()
    user = await UserRepository(session).create()
    scan = await ScanRepository(session).record(
        user_id=user.id,
        capture_ref="b",
        outcome=ScanOutcome.RESOLVED,
        training_consent=True,
    )

    await emit_scan(sink, scan)
    await emit_scan(sink, scan)

    assert len(sink.examples_of(TrainingExampleKind.SCAN)) == 1
