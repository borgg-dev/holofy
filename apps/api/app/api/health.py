"""Liveness/readiness endpoint.

Exposes the active provider backends and the data region so a deploy can be verified at a
glance — surfacing region drift matters because EU residency is a GDPR obligation, not a
preference.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.dependencies import get_settings
from app.config import Settings

router = APIRouter(tags=["meta"])


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
    data_region: str
    recognition_provider: str
    pricing_provider: str


@router.get("/health", response_model=HealthResponse)
async def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    return HealthResponse(
        status="ok",
        version=settings.api_version,
        environment=settings.environment,
        data_region=settings.data_region,
        recognition_provider=settings.recognition_provider,
        pricing_provider=settings.pricing_provider,
    )
