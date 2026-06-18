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

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# The dev-token backend's default signing secret. Safe only for `local`; a validator below
# refuses to boot with this value in any deployed environment.
INSECURE_DEV_SECRET = "dev-insecure-do-not-use-in-production"


class Environment(StrEnum):
    LOCAL = "local"
    STAGING = "staging"
    PRODUCTION = "production"


class RecognitionBackend(StrEnum):
    MOCK = "mock"


class PricingBackend(StrEnum):
    MOCK = "mock"
    TCGDEX = "tcgdex"


class AuthBackend(StrEnum):
    DEV_TOKEN = "dev_token"


class RateLimitBackend(StrEnum):
    MEMORY = "memory"


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

    # Auth seam: the dev-token backend mints/verifies an HMAC-signed bearer that maps to a
    # seeded user, so endpoints are genuinely user-scoped with no OAuth/Clerk yet. Real
    # federated identity drops in behind the same AuthProvider Protocol (see ADR 0004).
    auth_provider: AuthBackend = AuthBackend.DEV_TOKEN
    # Signs dev tokens. Required outside `local`; the default is dev-only and the validator
    # below refuses to boot a deployed environment that hasn't overridden it.
    auth_dev_secret: str = INSECURE_DEV_SECRET

    # Freemium COGS guard: the free ("Collector") tier is 8 ID scans/day (master plan §4).
    # The memory limiter is fine for a single process; the Redis backend lands behind the
    # same RateLimiter Protocol for the multi-instance gateway.
    rate_limit_provider: RateLimitBackend = RateLimitBackend.MEMORY
    free_tier_daily_scans: int = 8

    # Only consulted when pricing_provider == tcgdex. No key required — TCGdex is open.
    tcgdex_api_root: str = "https://api.tcgdex.net/v2"
    tcgdex_locale: str = "en"
    tcgdex_timeout_seconds: float = 10.0

    # Below this top-1 confidence the scan flow must ask the user to confirm rather than
    # commit a guess — getting a high-value variant wrong is the product's worst failure.
    recognition_confirm_threshold: float = 0.85

    log_level: str = "INFO"
    log_json: bool = True

    @model_validator(mode="after")
    def _require_real_dev_secret_when_deployed(self) -> "Settings":
        if self.environment is not Environment.LOCAL and self.auth_dev_secret == INSECURE_DEV_SECRET:
            raise ValueError(
                "HOLOFY_AUTH_DEV_SECRET must be overridden with a real secret outside the "
                "local environment"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
