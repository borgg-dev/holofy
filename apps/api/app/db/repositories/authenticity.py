from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.authenticity import AuthenticityRecord
from app.db.models.enums import AuthenticityRiskBand, AuthenticityStatus
from app.db.repositories._flush import flush_or_conflict
from app.db.types import utcnow
from app.schemas.authenticity import AuthenticityResponse


class AuthenticityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(
        self,
        response: AuthenticityResponse,
        *,
        user_id: uuid.UUID,
        capture_ref: str,
        card_id: uuid.UUID | None = None,
        training_consent: bool = False,
        consent_note: str | None = None,
    ) -> AuthenticityRecord:
        """Persist an authenticity result — risk band, refuse, or not-assessed — for the user.

        The band and signals are populated only on the ``assessed`` path; a ``retake`` or
        ``not_assessed`` stores its reasons and leaves the band null, so the outcomes are
        unambiguous in history. There is deliberately no boolean verdict column to write.

        ``training_consent`` defaults to ``False``: a screen is never added to the training
        corpus unless the user explicitly opted in for this capture; there is no path that
        flips it on by default.
        """
        assessment = response.assessment
        record = AuthenticityRecord(
            user_id=user_id,
            capture_ref=capture_ref,
            card_id=card_id,
            status=AuthenticityStatus(response.status.value),
            risk_band=(
                AuthenticityRiskBand(assessment.risk_band.value) if assessment else None
            ),
            confidence=assessment.confidence if assessment else None,
            reference_value_eur=assessment.reference_value_eur if assessment else None,
            signals=(
                [s.model_dump(mode="json") for s in assessment.signals] if assessment else []
            ),
            reasons=list(response.reasons or []),
            training_consent=training_consent,
            consent_note=consent_note,
        )
        self._session.add(record)
        await flush_or_conflict(self._session)
        return record

    async def revoke_training_consent_for_user(self, user_id: uuid.UUID) -> int:
        """Withdraw training consent across a user's screens; returns the count revoked.

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
        """Grant training consent across a user's existing screens; returns the count granted."""
        records = await self.list_for_user(user_id)
        granted = 0
        for record in records:
            if not record.training_consent:
                record.training_consent = True
                record.consent_revoked_at = None
                granted += 1
        await self._session.flush()
        return granted

    async def list_training_eligible(self) -> list[AuthenticityRecord]:
        """Screens the data lake may ingest: explicit consent, never revoked.

        The training pipeline reads through this method only, so the consent gate can't be
        bypassed by an ad-hoc query elsewhere.
        """
        stmt = select(AuthenticityRecord).where(
            AuthenticityRecord.training_consent.is_(True),
            AuthenticityRecord.consent_revoked_at.is_(None),
        )
        return list((await self._session.execute(stmt)).scalars())

    async def get(self, authenticity_id: uuid.UUID) -> AuthenticityRecord | None:
        return await self._session.get(AuthenticityRecord, authenticity_id)

    async def list_for_user(self, user_id: uuid.UUID) -> list[AuthenticityRecord]:
        stmt = (
            select(AuthenticityRecord)
            .where(AuthenticityRecord.user_id == user_id)
            .order_by(AuthenticityRecord.created_at.desc())
        )
        return list((await self._session.execute(stmt)).scalars())
