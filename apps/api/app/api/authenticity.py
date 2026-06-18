"""Authenticity endpoint — a capture in, a private risk *band* (or retake/not-assessed) out.

User-scoped and quota-guarded like the scan and pre-grade endpoints: the caller is resolved
from the bearer token, the free tier's daily budget is charged before any screening cost is
incurred, and the result — risk band, refuse, or below-threshold — is persisted as an
``AuthenticityRecord``.

The defamation guardrail (charter §3.5) is structural, not cosmetic:

- the response carries a three-band risk read and a disclaimer, never a fake/genuine verdict;
- a capture too poor to read is a typed ``retake`` (200), and a card below the value
  threshold is a typed ``not_assessed`` (200) — the client parses one shape, never a 500.

Two faults become an error envelope: an unresolvable capture reference (404
``capture_not_found``) and a ``card_id`` that isn't in the catalog (404 ``card_not_found``) —
the screen needs a resolved identity for the catalog cross-check and the value gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    get_authenticity_service,
    get_capture_store,
    get_current_user,
    get_datalake_sink,
    get_pricing_provider,
    get_rate_limiter,
    get_session,
    get_settings,
)
from app.authenticity.catalog_existence import CardTuple
from app.config import Settings
from app.core.errors import (
    CaptureNotFoundError,
    CardNotFoundError,
    PriceUnavailableError,
    QuotaExceededError,
)
from app.datalake.base import DataLakeSink
from app.datalake.emit import emit_authenticity
from app.db.models import User
from app.db.repositories import AuthenticityRepository, CardRepository
from app.grading.capture_store import CaptureNotFoundError as CaptureMissing
from app.grading.capture_store import CaptureStore
from app.providers.base import PricingProvider
from app.ratelimit.base import RateLimiter
from app.schemas.authenticity import AuthenticityRequest, AuthenticityResponse
from app.services.authenticity import AuthenticityService
from app.services.consent import build_consent_service

router = APIRouter(tags=["authenticity"])

# Authenticity screens draw on the same free-tier budget as scans and pre-grades — one quota
# key across the COGS-bearing endpoints, so it can't be sidestepped by hopping between them.
_AUTHENTICITY_QUOTA_KEY = "scan:{user_id}"


@dataclass(frozen=True, slots=True)
class _AuthenticityCaptureRef:
    """Satisfies the ``AuthenticityCapture`` Protocol the provider analyzes against."""

    capture_ref: str
    image_count: int


@router.post(
    "/authenticity",
    response_model=AuthenticityResponse,
    status_code=status.HTTP_200_OK,
)
async def assess_authenticity(
    request: AuthenticityRequest,
    user: User = Depends(get_current_user),
    service: AuthenticityService = Depends(get_authenticity_service),
    store: CaptureStore = Depends(get_capture_store),
    pricing: PricingProvider = Depends(get_pricing_provider),
    limiter: RateLimiter = Depends(get_rate_limiter),
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
    data_lake: DataLakeSink = Depends(get_datalake_sink),
) -> AuthenticityResponse:
    # Charge quota before spending a screening credit so abuse can't drive COGS.
    window = await limiter.check_and_consume(
        _AUTHENTICITY_QUOTA_KEY.format(user_id=user.id),
        limit=settings.free_tier_daily_scans,
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

    # The screen needs a resolved card for both the catalog cross-check and the value gate.
    card = await CardRepository(session).get_by_canonical_id(request.card_id)
    if card is None:
        raise CardNotFoundError(
            "This card isn't in the catalog yet — scan or look it up first.",
            details={"card_id": request.card_id},
        )

    # Confirm the capture actually resolves before screening. The authenticity provider
    # resolves the stills itself (it reads the foil across multiple angles), so — unlike
    # pre-grade, which needs the pixels in-process for centering — the endpoint only probes
    # that the upload exists, turning a stale/expired ref into a typed 404.
    try:
        await store.load(request.capture_ref)
    except CaptureMissing as exc:
        raise CaptureNotFoundError(
            "No capture was found for this reference.",
            details={"capture_ref": request.capture_ref},
        ) from exc

    capture = _AuthenticityCaptureRef(capture_ref=request.capture_ref, image_count=1)
    result = await service.assess(
        capture,
        card=CardTuple(
            set_code=card.set_code,
            collector_number=card.collector_number,
            variant=card.variant,
            language=card.language,
        ),
        value_eur=await _value_or_none(pricing, card.canonical_id),
    )

    # Each capture inherits the account's standing consent — never the wire flag directly.
    # An explicit opt-in grants the account first; otherwise the account preference governs.
    consent = await build_consent_service(session).resolve_for_capture(
        user, opt_in=request.training_consent, note=request.consent_note
    )

    record = await AuthenticityRepository(session).record(
        result,
        user_id=user.id,
        capture_ref=request.capture_ref,
        card_id=card.id,
        training_consent=consent.training_consent,
        consent_note=consent.consent_note,
    )
    # Close the consent loop: emit to the lake only when the screen carries standing consent.
    # The gate inside ``emit_authenticity`` no-ops a non-consented record, so a default
    # (consent-off) screen is the owner's private history and nothing more.
    await emit_authenticity(data_lake, record)
    return result


async def _value_or_none(
    pricing: PricingProvider, canonical_id: str
) -> Decimal | None:
    """The card's current € value for the value gate; a long-tail/unpriced card is ``None``.

    An unpriced card simply isn't screened (the gate treats ``None`` as below-threshold) —
    a missing price is a long-tail fact, not a fault.
    """
    try:
        quote = await pricing.price(canonical_id)
    except PriceUnavailableError:
        return None
    return quote.value
