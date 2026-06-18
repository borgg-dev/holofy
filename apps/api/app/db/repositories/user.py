from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self) -> User:
        user = User()
        self._session.add(user)
        await self._session.flush()
        return user

    async def get(self, user_id: uuid.UUID) -> User | None:
        return await self._session.get(User, user_id)

    async def get_by_auth(self, provider: str, subject: str) -> User | None:
        stmt = select(User).where(
            User.auth_provider == provider, User.auth_subject == subject
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def delete(self, user: User) -> None:
        """Erase a user and every owned row (collection, scans, snapshots) via cascade.

        Catalog and market data (``Card``, ``PriceObservation``) are reference data and are
        deliberately left intact; the data-lake purge of this user's training-eligible
        scans is handled separately — see ``app/db/erasure.py``.
        """
        await self._session.delete(user)
        await self._session.flush()
