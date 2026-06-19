"""Collection endpoints — add a card, list the holdings with current € valuations.

Every route is scoped to the bearer-resolved user; one collector can never read or write
another's holdings. Adding requires the card to exist in the catalog (a scan lands it
there), so the collection can't accrue cards the rest of the system doesn't know about.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_collection_service, get_current_user
from app.db.models import User
from app.schemas.collection import (
    AddCollectionItemRequest,
    CollectionItemValuation,
)
from app.services.collection import CollectionService

router = APIRouter(prefix="/collection", tags=["collection"])


@router.post(
    "",
    response_model=CollectionItemValuation,
    status_code=status.HTTP_201_CREATED,
)
async def add_to_collection(
    request: AddCollectionItemRequest,
    user: User = Depends(get_current_user),
    service: CollectionService = Depends(get_collection_service),
) -> CollectionItemValuation:
    return await service.add(user.id, request)


@router.get("", response_model=list[CollectionItemValuation])
async def list_collection(
    user: User = Depends(get_current_user),
    service: CollectionService = Depends(get_collection_service),
) -> list[CollectionItemValuation]:
    # A bare array of valued holdings; the client groups and totals them (the server total
    # still lives behind the portfolio endpoint, which the Vault header reads).
    result = await service.list_valued(user.id)
    return result.items
