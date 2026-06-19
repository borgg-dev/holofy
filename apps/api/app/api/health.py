"""Liveness/readiness endpoint.

Exposes the active provider backends and the data region so a deploy can be verified at a
glance — surfacing region drift matters because EU residency is a GDPR obligation, not a
preference.
"""

import logging

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_session, get_settings
from app.config import Settings

router = APIRouter(tags=["meta"])
logger = logging.getLogger("holofy.api")


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
    data_region: str
    recognition_provider: str
    pricing_provider: str


@router.get("/health", response_model=HealthResponse)
async def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    """Liveness: the process is up. Cheap and dependency-free so a load balancer's liveness
    probe never flaps on a transient DB blip — use ``/health/ready`` to gate traffic."""
    return HealthResponse(
        status="ok",
        version=settings.api_version,
        environment=settings.environment,
        data_region=settings.data_region,
        recognition_provider=settings.recognition_provider,
        pricing_provider=settings.pricing_provider,
    )


@router.get("/health/ready")
async def ready(session: AsyncSession = Depends(get_session)) -> JSONResponse:
    """Readiness: can this instance actually serve? Pings the database; a 503 tells the load
    balancer to route around this instance instead of sending it traffic it can't handle."""
    try:
        await session.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 - any DB failure means not-ready
        logger.warning("readiness check failed", exc_info=exc)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not_ready", "db": "down"},
        )
    return JSONResponse(status_code=status.HTTP_200_OK, content={"status": "ready", "db": "ok"})
