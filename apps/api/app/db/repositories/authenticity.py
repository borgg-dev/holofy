from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.authenticity import AuthenticityRecord
from app.db.models.enums import AuthenticityRiskBand, AuthenticityStatus
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
    ) -> AuthenticityRecord:
        """Persist an authenticity result — risk band, refuse, or not-assessed — for the user.

        The band and signals are populated only on the ``assessed`` path; a ``retake`` or
        ``not_assessed`` stores its reasons and leaves the band null, so the outcomes are
        unambiguous in history. There is deliberately no boolean verdict column to write.
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
        )
        self._session.add(record)
        await self._session.flush()
        return record

    async def get(self, authenticity_id: uuid.UUID) -> AuthenticityRecord | None:
        return await self._session.get(AuthenticityRecord, authenticity_id)

    async def list_for_user(self, user_id: uuid.UUID) -> list[AuthenticityRecord]:
        stmt = (
            select(AuthenticityRecord)
            .where(AuthenticityRecord.user_id == user_id)
            .order_by(AuthenticityRecord.created_at.desc())
        )
        return list((await self._session.execute(stmt)).scalars())
