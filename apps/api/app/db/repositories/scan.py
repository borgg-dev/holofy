from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.enums import ScanOutcome
from app.db.models.scan import ScanRecord
from app.db.types import utcnow


class ScanRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(
        self,
        *,
        user_id: uuid.UUID,
        capture_ref: str,
        outcome: ScanOutcome,
        candidates: list[dict[str, Any]] | None = None,
        top_confidence: float | None = None,
        resolved_card_id: uuid.UUID | None = None,
        training_consent: bool = False,
        consent_note: str | None = None,
    ) -> ScanRecord:
        """Log a scan event.

        ``training_consent`` defaults to ``False``: a scan is never added to the training
        corpus unless the user explicitly opted in. Callers pass ``True`` only when consent
        was given at capture; there is no path that flips it on by default.
        """
        scan = ScanRecord(
            user_id=user_id,
            capture_ref=capture_ref,
            outcome=outcome,
            candidates=candidates or [],
            top_confidence=top_confidence,
            resolved_card_id=resolved_card_id,
            training_consent=training_consent,
            consent_note=consent_note,
        )
        self._session.add(scan)
        await self._session.flush()
        return scan

    async def get(self, scan_id: uuid.UUID) -> ScanRecord | None:
        return await self._session.get(ScanRecord, scan_id)

    async def list_for_user(self, user_id: uuid.UUID) -> list[ScanRecord]:
        stmt = (
            select(ScanRecord)
            .where(ScanRecord.user_id == user_id)
            .order_by(ScanRecord.created_at.desc())
        )
        return list((await self._session.execute(stmt)).scalars())

    async def revoke_training_consent(self, scan: ScanRecord) -> None:
        """Withdraw consent: the scan stays in the user's history but is marked for purge
        from any derived training set (``consent_revoked_at`` stamped). Idempotent.
        """
        if not scan.training_consent and scan.consent_revoked_at is not None:
            return
        scan.training_consent = False
        scan.consent_revoked_at = utcnow()
        await self._session.flush()

    async def list_training_eligible(self) -> list[ScanRecord]:
        """Scans the data lake may ingest: explicit consent, never revoked.

        The training pipeline reads through this method only, so the consent gate can't be
        bypassed by an ad-hoc query elsewhere.
        """
        stmt = select(ScanRecord).where(
            ScanRecord.training_consent.is_(True),
            ScanRecord.consent_revoked_at.is_(None),
        )
        return list((await self._session.execute(stmt)).scalars())
