"""Typed application settings.

Holofy is an EU-first product, so a few of these defaults are compliance choices,
not preferences: the data region is pinned to the EU for GDPR residency, and CORS is
deny-by-default so a forgotten wildcard can't leak the API to arbitrary origins.

Everything external (recognition, pricing) is selected by a ``*_provider`` switch so the
whole app runs against mocks with no credentials, and a real provider drops in later
without touching call sites (see ADR 0001).
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    LOCAL = "local"
    STAGING = "staging"
    PRODUCTION = "production"


class RecognitionBackend(StrEnum):
    MOCK = "mock"


class PricingBackend(StrEnum):
    MOCK = "mock"
    TCGDEX = "tcgdex"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="HOLOFY_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Environment = Environment.LOCAL
    debug: bool = False

    api_title: str = "Holofy API"
    api_version: str = "0.1.0"

    # GDPR: all personal data (scan images, portfolios) must reside in the EU. This is
    # surfaced in the health payload so deployment region drift is observable, not silent.
    data_region: str = "eu-central-1"

    # Async SQLAlchemy URL. Postgres (asyncpg) is the prod target and must sit in the EU
    # region above; the local default is an aiosqlite file so the app runs with no DB
    # server. Tests override this with an in-memory SQLite URL.
    database_url: str = "sqlite+aiosqlite:///./holofy.db"
    database_echo: bool = False

    # Deny-by-default. Populate per environment with the exact mobile/web origins.
    cors_allow_origins: list[str] = Field(default_factory=list)

    recognition_provider: RecognitionBackend = RecognitionBackend.MOCK
    pricing_provider: PricingBackend = PricingBackend.MOCK

    # Only consulted when pricing_provider == tcgdex. No key required — TCGdex is open.
    tcgdex_api_root: str = "https://api.tcgdex.net/v2"
    tcgdex_locale: str = "en"
    tcgdex_timeout_seconds: float = 10.0

    # Below this top-1 confidence the scan flow must ask the user to confirm rather than
    # commit a guess — getting a high-value variant wrong is the product's worst failure.
    recognition_confirm_threshold: float = 0.85

    log_level: str = "INFO"
    log_json: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
