from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.enums import PregradeStatus
from app.db.models.pregrade import PreGradeRecord
from app.db.repositories._flush import flush_or_conflict
from app.db.types import utcnow
from app.schemas.grading import PregradeResponse


class PreGradeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(
        self,
        response: PregradeResponse,
        *,
        user_id: uuid.UUID,
        capture_ref: str,
        card_id: uuid.UUID | None = None,
        training_consent: bool = False,
        consent_note: str | None = None,
    ) -> PreGradeRecord:
        """Persist a pre-grade result — estimated range or a refuse — against the user.

        The probability columns are populated only on the ``estimated`` path; a ``retake``
        stores its reasons and leaves the range null, so the two outcomes are unambiguous in
        history. There is deliberately no single-grade column to write.

        ``training_consent`` defaults to ``False``: a pre-grade is never added to the training
        corpus unless the user explicitly opted in for this capture; there is no path that
        flips it on by default.
        """
        probability = response.probability
        record = PreGradeRecord(
            user_id=user_id,
            capture_ref=capture_ref,
            card_id=card_id,
            status=PregradeStatus(response.status.value),
            likely_low=probability.likely_low if probability else None,
            likely_high=probability.likely_high if probability else None,
            at_least=probability.at_least if probability else None,
            p_at_least=probability.p_at_least if probability else None,
            confidence=response.confidence,
            sub_scores=[s.model_dump(mode="json") for s in response.sub_scores or []],
            retake_reasons=list(response.reasons or []),
            training_consent=training_consent,
            consent_note=consent_note,
        )
        self._session.add(record)
        await flush_or_conflict(self._session)
        return record

    async def revoke_training_consent_for_user(self, user_id: uuid.UUID) -> int:
        """Withdraw training consent across a user's pre-grades; returns the count revoked.

        Mirrors the scan repository's account-level switch: only currently-consented records
        are touched, and the row is marked for lake purge (``consent_revoked_at`` stamped).
        """
        records = await self.list_for_user(user_id)
        revoked = 0
        for record in records:
            if record.training_consent:
                record.training_consent = False
                record.consent_revoked_at = utcnow()
                revoked += 1
        await self._session.flush()
        return revoked

    async def grant_training_consent_for_user(self, user_id: uuid.UUID) -> int:
        """Grant training consent across a user's existing pre-grades; returns the count granted."""
        records = await self.list_for_user(user_id)
        granted = 0
        for record in records:
            if not record.training_consent:
                record.training_consent = True
                record.consent_revoked_at = None
                granted += 1
        await self._session.flush()
        return granted

    async def list_training_eligible(self) -> list[PreGradeRecord]:
        """Pre-grades the data lake may ingest: explicit consent, never revoked.

        The training pipeline reads through this method only, so the consent gate can't be
        bypassed by an ad-hoc query elsewhere.
        """
        stmt = select(PreGradeRecord).where(
            PreGradeRecord.training_consent.is_(True),
            PreGradeRecord.consent_revoked_at.is_(None),
        )
        return list((await self._session.execute(stmt)).scalars())

    async def get(self, pregrade_id: uuid.UUID) -> PreGradeRecord | None:
        return await self._session.get(PreGradeRecord, pregrade_id)

    async def list_for_user(self, user_id: uuid.UUID) -> list[PreGradeRecord]:
        stmt = (
            select(PreGradeRecord)
            .where(PreGradeRecord.user_id == user_id)
            .order_by(PreGradeRecord.created_at.desc())
        )
        return list((await self._session.execute(stmt)).scalars())
