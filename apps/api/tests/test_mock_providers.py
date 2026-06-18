"""Coverage for the mock providers and the config-driven factory."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import pytest

from app.config import PricingBackend, RecognitionBackend, Settings
from app.core.errors import PriceUnavailableError
from app.providers.factory import build_pricing_provider, build_recognition_provider
from app.providers.pricing.mock import MockPricingProvider
from app.providers.pricing.tcgdex_provider import TcgdexPricingProvider
from app.providers.recognition.mock import MockRecognitionProvider
from app.schemas.cards import RecognitionResult


@dataclass
class _Bundle:
    bundle_id: str
    image_count: int = 1


@pytest.mark.asyncio
async def test_recognition_high_confidence_fixture_is_single_and_confident() -> None:
    result = await MockRecognitionProvider().recognize(_Bundle("mock-high-confidence"))

    assert isinstance(result, RecognitionResult)
    assert len(result.candidates) == 1
    assert result.top.confidence >= 0.85
    assert not result.needs_confirmation(0.85)


@pytest.mark.asyncio
async def test_recognition_low_confidence_fixture_trips_confirm_with_top_two() -> None:
    result = await MockRecognitionProvider().recognize(_Bundle("mock-low-confidence"))

    assert len(result.candidates) == 2
    assert result.needs_confirmation(0.85)
    # Candidates are the two same-name Charizard reprints — same art, different value.
    assert {c.identity.canonical_id for c in result.candidates} == {"base1-4", "base2-4"}


@pytest.mark.asyncio
async def test_recognition_unknown_bundle_defaults_to_low_confidence_case() -> None:
    result = await MockRecognitionProvider().recognize(_Bundle("anything-else"))
    assert result.needs_confirmation(0.85)


@pytest.mark.asyncio
async def test_mock_pricing_returns_known_quote() -> None:
    quote = await MockPricingProvider().price("base1-4")
    assert quote.value == Decimal("757.10")
    assert quote.currency == "EUR"
    assert quote.source == "mock"


@pytest.mark.asyncio
async def test_mock_pricing_unknown_card_raises_price_unavailable() -> None:
    with pytest.raises(PriceUnavailableError):
        await MockPricingProvider().price("does-not-exist")


def test_factory_defaults_to_mock_backends() -> None:
    settings = Settings()
    assert isinstance(build_recognition_provider(settings), MockRecognitionProvider)
    provider, client = build_pricing_provider(settings)
    assert isinstance(provider, MockPricingProvider)
    assert client is None


@pytest.mark.asyncio
async def test_factory_builds_tcgdex_pricing_and_owns_a_client() -> None:
    settings = Settings(pricing_provider=PricingBackend.TCGDEX)
    provider, client = build_pricing_provider(settings)
    try:
        assert isinstance(provider, TcgdexPricingProvider)
        assert client is not None
    finally:
        if client is not None:
            await client.aclose()


def test_factory_honours_recognition_backend_enum() -> None:
    settings = Settings(recognition_provider=RecognitionBackend.MOCK)
    assert isinstance(build_recognition_provider(settings), MockRecognitionProvider)
