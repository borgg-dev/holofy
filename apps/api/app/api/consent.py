"""Training-consent endpoints — the user's explicit, revocable grip on the moat.

Training consent is separate from app-usage consent and is off by default (architecture §6,
charter §3.5): a fresh account reads ``granted=false`` with nothing in the training lake, and
only an explicit opt-in changes that. These two routes are what the mobile privacy screen
binds to:

- ``GET /consent/training`` — read the current posture (granted + per-kind counts).
- ``PUT /consent/training`` — set it: ``{granted: true}`` opts in, ``{granted: false}`` revokes
  and marks the user's consented captures for purge from any derived training set.

User-scoped via the bearer token; the state is always the *caller's* own, never another
user's. No quota guard — managing your own privacy is never rate-limited.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_datalake_sink, get_session
from app.datalake.base import DataLakeSink
from app.db.models import User
from app.schemas.consent import ConsentState, ConsentUpdate
from app.services.consent import build_consent_service

router = APIRouter(prefix="/consent", tags=["consent"])


@router.get("/training", response_model=ConsentState, status_code=status.HTTP_200_OK)
async def read_training_consent(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ConsentState:
    return await build_consent_service(session).state(user)


@router.put("/training", response_model=ConsentState, status_code=status.HTTP_200_OK)
async def set_training_consent(
    update: ConsentUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    data_lake: DataLakeSink = Depends(get_datalake_sink),
) -> ConsentState:
    # The sink is wired so a revoke purges already-emitted lake examples (GDPR Art. 7(3)).
    service = build_consent_service(session, data_lake=data_lake)
    if update.granted:
        return await service.grant(user, note=update.note)
    return await service.revoke(user)
