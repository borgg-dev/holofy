"""Collection endpoints — add a card, list the holdings with current € valuations.

Every route is scoped to the bearer-resolved user; one collector can never read or write
another's holdings. Adding requires the card to exist in the catalog (a scan lands it
there), so the collection can't accrue cards the rest of the system doesn't know about.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Response, status

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


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def remove_from_collection(
    item_id: uuid.UUID,
    user: User = Depends(get_current_user),
    service: CollectionService = Depends(get_collection_service),
) -> Response:
    # Remove one holding from the Vault. Owner-scoped in the service: a 404 (not a 403) for an id
    # that isn't the caller's, so the endpoint never reveals another user's holding ids exist.
    await service.remove(user.id, item_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("", response_model=list[CollectionItemValuation])
async def list_collection(
    user: User = Depends(get_current_user),
    service: CollectionService = Depends(get_collection_service),
) -> list[CollectionItemValuation]:
    # A bare array of valued holdings; the client groups and totals them (the server total
    # still lives behind the portfolio endpoint, which the Vault header reads).
    result = await service.list_valued(user.id)
    return result.items
