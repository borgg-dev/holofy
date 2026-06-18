from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import PricingBackend, RecognitionBackend, Settings
from app.main import create_app


@pytest.fixture
def settings() -> Settings:
    # Fully mocked backends — the API suite must run with no network and no keys.
    return Settings(
        recognition_provider=RecognitionBackend.MOCK,
        pricing_provider=PricingBackend.MOCK,
        log_json=False,
        cors_allow_origins=["https://app.holofy.test"],
    )


@pytest.fixture
def client(settings: Settings):
    with TestClient(create_app(settings)) as test_client:
        yield test_client
