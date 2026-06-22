from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.collection import CollectionItem
from app.db.models.enums import CardCondition
from app.db.repositories._flush import flush_or_conflict


class CollectionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        *,
        user_id: uuid.UUID,
        card_id: uuid.UUID,
        condition: CardCondition,
        quantity: int = 1,
        acquired_price_eur: Decimal | None = None,
        acquired_on: date | None = None,
    ) -> CollectionItem:
        # A holding is unique on (user, card, condition); quantity carries duplicates within a
        # condition. So re-adding a card you already own at the same condition is not a conflict —
        # it means "I have one more": fold it into the existing row's quantity. This is the common
        # case (scanning a second copy, or re-tapping Add) and previously failed with a 409 that
        # the app surfaced as "couldn't add to vault".
        existing = await self._find(user_id=user_id, card_id=card_id, condition=condition)
        if existing is not None:
            existing.quantity += quantity
            # Backfill acquisition facts only if the original row lacked them, so re-adding never
            # erases a price/date the user already recorded.
            if existing.acquired_price_eur is None and acquired_price_eur is not None:
                existing.acquired_price_eur = acquired_price_eur
            if existing.acquired_on is None and acquired_on is not None:
                existing.acquired_on = acquired_on
            await flush_or_conflict(self._session)
            return existing

        item = CollectionItem(
            user_id=user_id,
            card_id=card_id,
            condition=condition,
            quantity=quantity,
            acquired_price_eur=acquired_price_eur,
            acquired_on=acquired_on,
        )
        self._session.add(item)
        # A non-positive quantity (or a racing insert of the same holding) violates a constraint;
        # surface it as a typed conflict rather than a 500.
        await flush_or_conflict(self._session)
        return item

    async def _find(
        self, *, user_id: uuid.UUID, card_id: uuid.UUID, condition: CardCondition
    ) -> CollectionItem | None:
        stmt = select(CollectionItem).where(
            CollectionItem.user_id == user_id,
            CollectionItem.card_id == card_id,
            CollectionItem.condition == condition,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_for_user(self, user_id: uuid.UUID) -> list[CollectionItem]:
        """The user's holdings with their cards eager-loaded, for valuation and display."""
        stmt = (
            select(CollectionItem)
            .where(CollectionItem.user_id == user_id)
            .options(selectinload(CollectionItem.card))
            .order_by(CollectionItem.created_at)
        )
        return list((await self._session.execute(stmt)).scalars())
