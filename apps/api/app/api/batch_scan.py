"""Stack/batch scan endpoint — a pile of captures in, deduped per-card results out.

Stack mode (master plan §6, architecture §3.1): the user flips through cards while the client
samples frames and uploads a bundle per detection. The server identifies + prices each — **ID
+ value only** — dedupes near-identical detections, and returns a per-card list for the client
to confirm at the end of the stack.

User-scoped and quota-guarded exactly like ``/scan``: the free tier's daily budget is charged
**per capture, before recognition** (recognition is the credit), so a batch can't drive COGS
past the day's budget any more than firing single scans could. The endpoint stays thin — quota,
dedupe, persistence and the consent stamp all live in the service; faults surface through the
shared ``HolofyError`` handlers.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    get_batch_scan_service,
    get_current_user,
    get_session,
)
from app.db.models import User
from app.db.repositories import CardRepository, ScanRepository
from app.schemas.batch_scan import BatchScanRequest, BatchScanResponse
from app.services.batch_scan import BatchScanService
from app.services.consent import build_consent_service

router = APIRouter(tags=["scan"])


@router.post(
    "/scan/batch", response_model=BatchScanResponse, status_code=status.HTTP_200_OK
)
async def scan_batch(
    request: BatchScanRequest,
    user: User = Depends(get_current_user),
    service: BatchScanService = Depends(get_batch_scan_service),
    session: AsyncSession = Depends(get_session),
) -> BatchScanResponse:
    # The whole batch inherits the account's standing training consent — never a per-request
    # flag. A stack scan carries no at-capture opt-in (the first-capture consent prompt is a
    # single-card moment); existing standing consent governs every record this batch writes.
    consent = await build_consent_service(session).resolve_for_capture(
        user, opt_in=False, note=None
    )

    return await service.scan_batch(
        request.items,
        user_id=user.id,
        scans=ScanRepository(session),
        cards=CardRepository(session),
        training_consent=consent.training_consent,
        consent_note=consent.consent_note,
    )
