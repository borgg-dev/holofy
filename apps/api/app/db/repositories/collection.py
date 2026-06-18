from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.collection import CollectionItem
from app.db.models.enums import CardCondition


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
        item = CollectionItem(
            user_id=user_id,
            card_id=card_id,
            condition=condition,
            quantity=quantity,
            acquired_price_eur=acquired_price_eur,
            acquired_on=acquired_on,
        )
        self._session.add(item)
        await self._session.flush()
        return item

    async def list_for_user(self, user_id: uuid.UUID) -> list[CollectionItem]:
        """The user's holdings with their cards eager-loaded, for valuation and display."""
        stmt = (
            select(CollectionItem)
            .where(CollectionItem.user_id == user_id)
            .options(selectinload(CollectionItem.card))
            .order_by(CollectionItem.created_at)
        )
        return list((await self._session.execute(stmt)).scalars())
