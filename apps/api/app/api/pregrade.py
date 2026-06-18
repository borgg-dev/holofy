"""Pre-grade endpoint — a capture in, an honest grade *probability range* (or a retake) out.

User-scoped and quota-guarded like the scan endpoint: the caller is resolved from the
bearer token, the free tier's daily budget is charged before any grading cost is incurred,
and the result — estimated range or refuse — is persisted as a ``PreGradeRecord``.

Honest framing (charter §3.1) is structural, not cosmetic:

- the response carries a probability range and a disclaimer, never a single grade;
- a capture too poor to grade is a typed ``retake`` body with a 200, not a 500 — the client
  parses one shape whether it got an estimate or a "shoot it again".

The only fault that becomes an error envelope is an unresolvable capture reference (an
unknown/expired upload), which is a 404, distinct from a gradeable-but-poor capture.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    get_capture_store,
    get_current_user,
    get_pregrade_service,
    get_rate_limiter,
    get_session,
    get_settings,
)
from app.config import Settings
from app.core.errors import CaptureNotFoundError, QuotaExceededError
from app.db.models import User
from app.db.repositories import CardRepository, PreGradeRepository
from app.grading.capture_store import CaptureNotFoundError as CaptureMissing
from app.grading.capture_store import CaptureStore
from app.ratelimit.base import RateLimiter
from app.schemas.grading import PregradeRequest, PregradeResponse
from app.services.pregrade import PregradeService

router = APIRouter(tags=["pregrade"])

# Pre-grades draw on the same free-tier budget as scans — they share the recognition COGS
# guard so a single quota key can't be sidestepped by hitting the other endpoint.
_PREGRADE_QUOTA_KEY = "scan:{user_id}"


@dataclass(frozen=True, slots=True)
class _GradingCaptureRef:
    """Satisfies the ``GradingCapture`` Protocol the provider scores against."""

    capture_ref: str
    image_count: int


@router.post("/pregrade", response_model=PregradeResponse, status_code=status.HTTP_200_OK)
async def pregrade(
    request: PregradeRequest,
    user: User = Depends(get_current_user),
    service: PregradeService = Depends(get_pregrade_service),
    store: CaptureStore = Depends(get_capture_store),
    limiter: RateLimiter = Depends(get_rate_limiter),
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
) -> PregradeResponse:
    # Charge quota before spending a grading credit so abuse can't drive COGS.
    window = await limiter.check_and_consume(
        _PREGRADE_QUOTA_KEY.format(user_id=user.id), limit=settings.free_tier_daily_scans
    )
    if not window.allowed:
        raise QuotaExceededError(
            "Daily scan limit reached for your plan.",
            details={
                "limit": window.limit,
                "reset_seconds": window.reset_seconds,
                "plan": "free",
            },
        )

    try:
        image = await store.load(request.capture_ref)
    except CaptureMissing as exc:
        raise CaptureNotFoundError(
            "No capture was found for this reference.",
            details={"capture_ref": request.capture_ref},
        ) from exc

    capture = _GradingCaptureRef(capture_ref=request.capture_ref, image_count=1)
    result = await service.pregrade(capture, image=image)

    # Persist against the user (and the card, if this capture is of a resolved one) — the
    # user's pre-grade history and, with the eventual real grade, the model's training row.
    card_id = await _resolve_card_id(session, request.card_id)
    await PreGradeRepository(session).record(
        result,
        user_id=user.id,
        capture_ref=request.capture_ref,
        card_id=card_id,
    )
    return result


async def _resolve_card_id(session: AsyncSession, canonical_id: str | None):
    """Map an optional catalog ``canonical_id`` to its row id, ignoring an unknown one.

    A pre-grade is still valid history without a resolved card, so a stale/unknown id simply
    leaves the link null rather than failing the whole pre-grade.
    """
    if canonical_id is None:
        return None
    card = await CardRepository(session).get_by_canonical_id(canonical_id)
    return card.id if card is not None else None
