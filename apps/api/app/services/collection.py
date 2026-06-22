"""Collection orchestration: add a card, and value the holdings in €.

The valuation joins each holding to a current € quote from the pricing provider. The quote
is the catalog trend for the card; a per-condition adjustment is a later refinement, so the
honest read today is "catalog value × quantity", with a holding left unvalued (not zeroed)
when the long-tail card has no price. SQL stays in the repositories — this layer composes
them with the pricing seam.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from app.core.errors import (
    CardNotFoundError,
    CollectionItemNotFoundError,
    PriceUnavailableError,
)
from app.db.models.collection import CollectionItem
from app.db.repositories import CardRepository, CollectionRepository
from app.providers.base import PricingProvider
from app.schemas.cards import CardIdentity, PriceQuote, Variant
from app.schemas.collection import (
    AddCollectionItemRequest,
    CollectionItemValuation,
    CollectionResponse,
)


class CollectionService:
    def __init__(
        self,
        *,
        cards: CardRepository,
        collection: CollectionRepository,
        pricing: PricingProvider,
    ) -> None:
        self._cards = cards
        self._collection = collection
        self._pricing = pricing

    async def add(
        self, user_id: uuid.UUID, request: AddCollectionItemRequest
    ) -> CollectionItemValuation:
        """Add a scanned/looked-up card to the user's collection.

        The card must already exist in the catalog (a scan lands it there, or the nightly
        reference sync does); an unknown id is a 404 rather than an implicit catalog write,
        so the collection can't accrue phantom cards.
        """
        card = await self._cards.get_by_canonical_id(request.canonical_id)
        if card is None:
            raise CardNotFoundError(
                "No catalog card for this id — scan or look it up first.",
                details={"canonical_id": request.canonical_id},
            )
        item = await self._collection.add(
            user_id=user_id,
            card_id=card.id,
            condition=request.condition,
            quantity=request.quantity,
            acquired_price_eur=request.acquired_price_eur,
            acquired_on=request.acquired_on,
        )
        # Reuse the loaded card so the valuation doesn't re-query for the relationship.
        item.card = card
        return await self._value_item(item)

    async def remove(self, user_id: uuid.UUID, item_id: uuid.UUID) -> None:
        """Remove a holding from the user's collection. A missing/foreign id is a 404 — the
        delete is owner-scoped, so a user can only ever remove their own card."""
        removed = await self._collection.remove(user_id=user_id, item_id=item_id)
        if not removed:
            raise CollectionItemNotFoundError(
                "No such card in your collection.",
                details={"item_id": str(item_id)},
            )

    async def list_valued(self, user_id: uuid.UUID) -> CollectionResponse:
        items = await self._collection.list_for_user(user_id)
        valued = [await self._value_item(item) for item in items]
        total = sum(
            (v.line_value_eur for v in valued if v.line_value_eur is not None),
            Decimal("0.00"),
        )
        return CollectionResponse(items=valued, total_value_eur=total)

    async def _value_item(self, item: CollectionItem) -> CollectionItemValuation:
        quote = await self._quote_or_none(item.card.canonical_id)
        unit = quote.value if quote is not None else None
        line = unit * item.quantity if unit is not None else None
        return CollectionItemValuation(
            id=str(item.id),
            identity=_identity_of(item.card),
            condition=item.condition,
            quantity=item.quantity,
            acquired_price_eur=item.acquired_price_eur,
            acquired_on=item.acquired_on,
            price=quote,
            unit_value_eur=unit,
            line_value_eur=line,
            valued_at=quote.as_of if quote is not None else None,
            price_source=quote.source if quote is not None else None,
        )

    async def _quote_or_none(self, canonical_id: str) -> PriceQuote | None:
        try:
            return await self._pricing.price(canonical_id)
        except (PriceUnavailableError, CardNotFoundError):
            return None


def _identity_of(card) -> CardIdentity:  # noqa: ANN001 - ORM Card, no import cycle
    return CardIdentity(
        canonical_id=card.canonical_id,
        name=card.name,
        set_name=card.set_name,
        collector_number=card.collector_number,
        language=card.language,
        variant=Variant(card.variant),
        image_url=card.image_url,
    )
