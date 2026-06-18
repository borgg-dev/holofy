"""Training-consent orchestration — read and set the account-level moat permission.

The account flag on ``User`` is the durable source of truth: ``state`` reads it directly, so a
user who opts in *before* having any captures reads back ``granted=true`` and the setting
sticks. The per-kind counts ride alongside as supplementary detail ("12 scans are helping"),
no longer the thing that decides ``granted``.

Grant/revoke set the account preference and, in the same transaction, fan across the three
capture repositories so the user's *existing* captures match their new intent — a grant opts
history in, a revoke marks it for the erasure path's lake purge. Future captures inherit the
account flag at capture time (the scan / pre-grade / authenticity endpoints stamp each record
from it), so a user who opts in keeps contributing without re-consenting, and a revoke stops
future emissions immediately.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.db.repositories import (
    AuthenticityRepository,
    PreGradeRepository,
    ScanRepository,
    UserRepository,
)
from app.schemas.consent import ConsentCounts, ConsentState


@dataclass(frozen=True, slots=True)
class CaptureConsent:
    """The consent stamp a capture endpoint writes onto a new record, resolved from the account."""

    training_consent: bool
    consent_note: str | None


class ConsentService:
    def __init__(
        self,
        *,
        users: UserRepository,
        scans: ScanRepository,
        pregrades: PreGradeRepository,
        authenticity: AuthenticityRepository,
    ) -> None:
        self._users = users
        self._scans = scans
        self._pregrades = pregrades
        self._authenticity = authenticity

    async def state(self, user: User) -> ConsentState:
        """The account's training-consent posture: ``granted`` read straight off the account."""
        counts = await self._counts(user.id)
        return ConsentState(granted=user.training_consent, consented=counts)

    async def grant(self, user: User, *, note: str | None = None) -> ConsentState:
        """Opt the account in, then bring existing captures in line, and report the new state."""
        await self._users.grant_training_consent(user, note=note)
        await self._scans.grant_training_consent_for_user(user.id)
        await self._pregrades.grant_training_consent_for_user(user.id)
        await self._authenticity.grant_training_consent_for_user(user.id)
        return await self.state(user)

    async def revoke(self, user: User) -> ConsentState:
        """Opt the account out: revoke the account flag and every consented capture."""
        await self._users.revoke_training_consent(user)
        await self._scans.revoke_training_consent_for_user(user.id)
        await self._pregrades.revoke_training_consent_for_user(user.id)
        await self._authenticity.revoke_training_consent_for_user(user.id)
        return await self.state(user)

    async def resolve_for_capture(
        self, user: User, *, opt_in: bool, note: str | None
    ) -> CaptureConsent:
        """The consent a new capture is stamped with — derived from the account, never the wire.

        A capture inherits the account's standing preference: a record is training-eligible iff
        the account is currently consented. The request's ``opt_in`` is an at-capture *grant*
        (the first-capture prompt's "yes"), not a per-record flag — when it's set, the account
        is opted in first, so this and every future capture inherit it. The returned note rides
        with the record for audit; an account that isn't consented stamps the record off.
        """
        if opt_in and not user.training_consent:
            await self.grant(user, note=note)
        consented = user.training_consent and user.training_consent_revoked_at is None
        return CaptureConsent(
            training_consent=consented,
            consent_note=user.consent_note if consented else None,
        )

    async def _counts(self, user_id: uuid.UUID) -> ConsentCounts:
        # Count the user's *eligible* captures per kind — consented and never revoked — by
        # filtering their own records through the same predicate the lake ingest uses.
        scans = [
            s
            for s in await self._scans.list_for_user(user_id)
            if s.training_consent and s.consent_revoked_at is None
        ]
        pregrades = [
            p
            for p in await self._pregrades.list_for_user(user_id)
            if p.training_consent and p.consent_revoked_at is None
        ]
        screens = [
            a
            for a in await self._authenticity.list_for_user(user_id)
            if a.training_consent and a.consent_revoked_at is None
        ]
        return ConsentCounts(
            scans=len(scans),
            pregrades=len(pregrades),
            authenticity=len(screens),
        )


def build_consent_service(session: AsyncSession) -> ConsentService:
    """Assemble the service over one request session — the capture endpoints and the consent
    routes both stamp captures / set the account through this single composition.
    """
    return ConsentService(
        users=UserRepository(session),
        scans=ScanRepository(session),
        pregrades=PreGradeRepository(session),
        authenticity=AuthenticityRepository(session),
    )
