from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.enums import PregradeStatus
from app.db.models.pregrade import PreGradeRecord
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
    ) -> PreGradeRecord:
        """Persist a pre-grade result — estimated range or a refuse — against the user.

        The probability columns are populated only on the ``estimated`` path; a ``retake``
        stores its reasons and leaves the range null, so the two outcomes are unambiguous in
        history. There is deliberately no single-grade column to write.
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
        )
        self._session.add(record)
        await self._session.flush()
        return record

    async def get(self, pregrade_id: uuid.UUID) -> PreGradeRecord | None:
        return await self._session.get(PreGradeRecord, pregrade_id)

    async def list_for_user(self, user_id: uuid.UUID) -> list[PreGradeRecord]:
        stmt = (
            select(PreGradeRecord)
            .where(PreGradeRecord.user_id == user_id)
            .order_by(PreGradeRecord.created_at.desc())
        )
        return list((await self._session.execute(stmt)).scalars())
