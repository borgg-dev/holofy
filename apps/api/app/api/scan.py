"""Scan endpoint — capture bundle in, identified + priced card (or a confirm prompt) out.

User-scoped and quota-guarded: the caller is resolved from the bearer token, the free tier's
daily scan budget is enforced before any recognition cost is incurred, and the scan is
persisted as a ``ScanRecord`` (consent off by default). Provider and domain faults surface
through the shared ``HolofyError`` handlers, so this layer stays thin.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    get_current_user,
    get_rate_limiter,
    get_scan_service,
    get_session,
    get_settings,
)
from app.config import Settings
from app.core.errors import QuotaExceededError
from app.db.models import User
from app.db.repositories import CardRepository, ScanRepository
from app.ratelimit.base import RateLimiter
from app.schemas.scan import CaptureBundleRef, ScanResponse
from app.services.consent import build_consent_service
from app.services.scan import ScanService

router = APIRouter(tags=["scan"])

_SCAN_QUOTA_KEY = "scan:{user_id}"


@router.post("/scan", response_model=ScanResponse, status_code=status.HTTP_200_OK)
async def scan(
    bundle: CaptureBundleRef,
    user: User = Depends(get_current_user),
    service: ScanService = Depends(get_scan_service),
    limiter: RateLimiter = Depends(get_rate_limiter),
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
) -> ScanResponse:
    # Charge quota before spending a recognition credit so abuse can't drive COGS.
    window = await limiter.check_and_consume(
        _SCAN_QUOTA_KEY.format(user_id=user.id), limit=settings.free_tier_daily_scans
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

    # Each capture inherits the account's standing consent — never the wire flag directly.
    # An explicit opt-in on the bundle grants the account first, so this and future scans
    # carry it; otherwise the account preference (off by default) governs.
    consent = await build_consent_service(session).resolve_for_capture(
        user, opt_in=bundle.training_consent, note=bundle.consent_note
    )

    return await service.scan(
        bundle,
        user_id=user.id,
        scans=ScanRepository(session),
        cards=CardRepository(session),
        training_consent=consent.training_consent,
        consent_note=consent.consent_note,
    )
