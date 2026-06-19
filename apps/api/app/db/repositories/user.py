from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User
from app.db.repositories._flush import flush_or_conflict
from app.db.types import utcnow


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        auth_provider: str | None = None,
        auth_subject: str | None = None,
        email: str | None = None,
        password_hash: str | None = None,
    ) -> User:
        """Provision a user, optionally linked to an external identity or a password account.

        The auth pair is set together (the table's uniqueness guard requires both or
        neither); a keyless call still yields a usable anonymous account. ``email`` /
        ``password_hash`` are set for a registered password account and left null otherwise.
        """
        user = User(
            auth_provider=auth_provider,
            auth_subject=auth_subject,
            email=email,
            password_hash=password_hash,
        )
        self._session.add(user)
        # A racing provision of the same identity (or email) hits the unique guards; surface it
        # as a typed conflict rather than a 500.
        await flush_or_conflict(self._session)
        return user

    async def get(self, user_id: uuid.UUID) -> User | None:
        return await self._session.get(User, user_id)

    async def get_by_auth(self, provider: str, subject: str) -> User | None:
        stmt = select(User).where(
            User.auth_provider == provider, User.auth_subject == subject
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        """Find a password account by its (already-normalized) email login handle."""
        stmt = select(User).where(User.email == email)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def grant_training_consent(
        self, user: User, *, note: str | None = None
    ) -> None:
        """Opt the account into training-data use — the durable grant the privacy screen sets.

        Stamps the grant and clears any prior revocation (the row can't hold consent *and* a
        revocation, per the check constraint), so a re-opt-in cleanly re-enables the account.
        Idempotent: re-granting an already-consented account just refreshes the note.
        """
        user.training_consent = True
        user.training_consent_at = utcnow()
        user.training_consent_revoked_at = None
        user.consent_note = note
        await self._session.flush()

    async def revoke_training_consent(self, user: User) -> None:
        """Opt the account out — future captures stop carrying consent immediately.

        Clearing the flag and stamping the revocation is enough to gate *future* emissions;
        the purge of already-shared captures is the erasure path's job (``app/db/erasure.py``).
        Idempotent: a re-revoke keeps the original revocation stamp.
        """
        if not user.training_consent and user.training_consent_revoked_at is not None:
            return
        user.training_consent = False
        user.training_consent_revoked_at = utcnow()
        await self._session.flush()

    async def delete(self, user: User) -> None:
        """Erase a user and every owned row (collection, scans, snapshots) via cascade.

        Catalog and market data (``Card``, ``PriceObservation``) are reference data and are
        deliberately left intact; the data-lake purge of this user's training-eligible
        scans is handled separately — see ``app/db/erasure.py``.
        """
        await self._session.delete(user)
        await self._session.flush()
