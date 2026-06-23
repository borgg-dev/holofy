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
    get_datalake_sink,
    get_pregrade_service,
    get_pricing_provider,
    get_rate_limiter,
    get_session,
    get_settings,
)
from app.config import Settings
from app.core.errors import (
    CaptureNotFoundError,
    CardNotFoundError,
    PriceUnavailableError,
    QuotaExceededError,
)
from app.datalake.base import DataLakeSink
from app.datalake.emit import emit_pregrade
from app.db.models import User
from app.db.repositories import CollectionRepository
from app.providers.base import PricingProvider
from app.db.repositories import CardRepository, PreGradeRepository
from app.grading.capture_store import CaptureNotFoundError as CaptureMissing
from app.grading.capture_store import CaptureStore
from app.ratelimit.base import RateLimiter
from app.schemas.grading import PregradeRequest, PregradeResponse
from app.services.consent import build_consent_service
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
    pricing: PricingProvider = Depends(get_pricing_provider),
    limiter: RateLimiter = Depends(get_rate_limiter),
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
    data_lake: DataLakeSink = Depends(get_datalake_sink),
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

    # The card being graded (if this capture was resolved to one) — its near-mint guide price is the
    # baseline the service scales by the estimated condition into a "your copy" value.
    card_obj = (
        await CardRepository(session).get_by_canonical_id(request.card_id)
        if request.card_id
        else None
    )
    capture = _GradingCaptureRef(
        capture_ref=request.capture_ref, image_count=request.image_count
    )
    result = await service.pregrade(
        capture, image=image, reference_value_eur=await _baseline_value(pricing, card_obj)
    )

    # Persist the detected condition back onto the user's holding, if the pre-grade named one — so
    # the Vault reflects what the app assessed (the whole point: the app categorises the card, not
    # the user). Owner-scoped; a missing/foreign item is silently ignored.
    if request.collection_item_id is not None and result.estimated_condition is not None:
        await CollectionRepository(session).set_condition(
            user_id=user.id, item_id=request.collection_item_id, condition=result.estimated_condition
        )

    # Each capture inherits the account's standing consent — never the wire flag directly.
    # An explicit opt-in grants the account first; otherwise the account preference governs.
    consent = await build_consent_service(session).resolve_for_capture(
        user, opt_in=request.training_consent, note=request.consent_note
    )

    # Persist against the user (and the card, if this capture is of a resolved one) — the
    # user's pre-grade history and, with the eventual real grade, the model's training row.
    card_id = await _resolve_card_id(session, request.card_id)
    record = await PreGradeRepository(session).record(
        result,
        user_id=user.id,
        capture_ref=request.capture_ref,
        card_id=card_id,
        training_consent=consent.training_consent,
        consent_note=consent.consent_note,
    )
    # Close the consent loop: emit to the lake only when the pre-grade carries standing
    # consent. The gate inside ``emit_pregrade`` no-ops a non-consented record, so a default
    # (consent-off) pre-grade is the user's history and nothing more.
    await emit_pregrade(data_lake, record)
    return result


async def _baseline_value(pricing: PricingProvider, card_obj):  # noqa: ANN001
    """The card's near-mint guide value, or ``None`` when it isn't priceable — a missing price is a
    long-tail fact, never a reason to fail the pre-grade."""
    if card_obj is None:
        return None
    try:
        quote = await pricing.price(
            card_obj.canonical_id, name=card_obj.name, collector_number=card_obj.collector_number
        )
        return quote.value
    except (PriceUnavailableError, CardNotFoundError):
        return None


async def _resolve_card_id(session: AsyncSession, canonical_id: str | None):
    """Map an optional catalog ``canonical_id`` to its row id, ignoring an unknown one.

    A pre-grade is still valid history without a resolved card, so a stale/unknown id simply
    leaves the link null rather than failing the whole pre-grade.
    """
    if canonical_id is None:
        return None
    card = await CardRepository(session).get_by_canonical_id(canonical_id)
    return card.id if card is not None else None
