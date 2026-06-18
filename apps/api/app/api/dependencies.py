"""FastAPI dependency providers.

Providers are built once at startup (see ``app.main`` lifespan) and stashed on
``app.state``; these accessors hand them to routes. The ``ScanService`` is cheap and
stateless, so it is assembled per request from the long-lived providers.
"""

from __future__ import annotations

from fastapi import Depends, Request

from app.config import Settings
from app.providers.base import PricingProvider, RecognitionProvider
from app.services.scan import ScanService


def get_settings(request: Request) -> Settings:
    """The settings the app was built with — read from state, not the module cache, so a
    test that constructs an app with overridden settings sees them everywhere.
    """
    return request.app.state.settings


def get_recognition_provider(request: Request) -> RecognitionProvider:
    return request.app.state.recognition_provider


def get_pricing_provider(request: Request) -> PricingProvider:
    return request.app.state.pricing_provider


def get_scan_service(
    settings: Settings = Depends(get_settings),
    recognition: RecognitionProvider = Depends(get_recognition_provider),
    pricing: PricingProvider = Depends(get_pricing_provider),
) -> ScanService:
    return ScanService(
        recognition=recognition,
        pricing=pricing,
        confirm_threshold=settings.recognition_confirm_threshold,
    )
