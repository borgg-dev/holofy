from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.card import Card
from app.db.models.enums import Variant
from app.db.repositories._flush import flush_or_conflict


class CardRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, card_id: uuid.UUID) -> Card | None:
        return await self._session.get(Card, card_id)

    async def get_by_canonical_id(self, canonical_id: str) -> Card | None:
        """Resolve the catalog row for a pricing key — the scan loop's hot lookup."""
        stmt = select(Card).where(Card.canonical_id == canonical_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def upsert(
        self,
        *,
        canonical_id: str,
        name: str,
        set_name: str,
        set_code: str,
        collector_number: str,
        language: str,
        variant: Variant,
        image_url: str | None = None,
    ) -> Card:
        """Idempotently land a catalog entry — the shape the nightly reference sync uses."""
        existing = await self.get_by_canonical_id(canonical_id)
        if existing is not None:
            existing.name = name
            existing.set_name = set_name
            existing.set_code = set_code
            existing.collector_number = collector_number
            existing.language = language
            existing.variant = variant
            # Only overwrite a stored image with a real one — a later read that couldn't
            # resolve the artwork must not blank out an image we already have.
            if image_url is not None:
                existing.image_url = image_url
            await self._session.flush()
            return existing
        card = Card(
            canonical_id=canonical_id,
            name=name,
            set_name=set_name,
            set_code=set_code,
            collector_number=collector_number,
            language=language,
            variant=variant,
            image_url=image_url,
        )
        self._session.add(card)
        # A racing insert of the same canonical id hits the unique guard; surface it as a
        # typed conflict rather than a 500.
        await flush_or_conflict(self._session)
        return card
