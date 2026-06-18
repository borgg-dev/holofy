"""Provider selection by configuration.

The one place that decides which implementation backs each Protocol. Call sites depend on
the Protocol, never on a concrete class, so flipping ``HOLOFY_PRICING_PROVIDER`` from
``mock`` to ``tcgdex`` swaps the real Cardmarket path in with no code change elsewhere.

The TCGdex provider owns a pooled HTTP client, so it is built once per process and closed
on shutdown; the factory returns that singleton rather than a fresh client per request.
"""

from __future__ import annotations

from app.config import PricingBackend, RecognitionBackend, Settings
from app.providers.base import PricingProvider, RecognitionProvider
from app.providers.pricing.mock import MockPricingProvider
from app.providers.pricing.tcgdex import TcgdexClient
from app.providers.pricing.tcgdex_provider import TcgdexPricingProvider
from app.providers.recognition.mock import MockRecognitionProvider


def build_recognition_provider(settings: Settings) -> RecognitionProvider:
    match settings.recognition_provider:
        case RecognitionBackend.MOCK:
            return MockRecognitionProvider()


def build_pricing_provider(
    settings: Settings,
) -> tuple[PricingProvider, TcgdexClient | None]:
    """Return the configured pricing provider and the HTTP client it owns, if any.

    The caller (app lifespan) keeps the client to close it on shutdown; for the mock there
    is nothing to close, hence ``None``.
    """
    match settings.pricing_provider:
        case PricingBackend.MOCK:
            return MockPricingProvider(), None
        case PricingBackend.TCGDEX:
            client = TcgdexClient(
                api_root=settings.tcgdex_api_root,
                locale=settings.tcgdex_locale,
                timeout_seconds=settings.tcgdex_timeout_seconds,
            )
            return TcgdexPricingProvider(client), client
