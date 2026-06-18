"""Scan endpoint — capture bundle in, identified + priced card (or a confirm prompt) out.

A stub in the sense that it does not yet write to a portfolio or kick off async grading;
it is the wired contract the real Phase-1 flow extends. Provider faults surface through the
shared ``HolofyError`` handlers, so this layer stays thin.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_scan_service
from app.schemas.scan import CaptureBundleRef, ScanResponse
from app.services.scan import ScanService

router = APIRouter(tags=["scan"])


@router.post("/scan", response_model=ScanResponse, status_code=status.HTTP_200_OK)
async def scan(
    bundle: CaptureBundleRef,
    service: ScanService = Depends(get_scan_service),
) -> ScanResponse:
    return await service.scan(bundle)
