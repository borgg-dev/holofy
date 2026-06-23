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
    # Our owned pipeline: card detect/crop → OCR (RapidOCR, on-device-class CPU) → collector
    # number + name → catalog resolve. No per-scan vendor fee; the rented seam is gone.
    INHOUSE = "inhouse"


class CatalogBackend(StrEnum):
    # The card catalog the in-house recognizer resolves reads against. ``inmemory`` is a
    # handful of seed cards (dev/test); ``tcgdex`` resolves the live Pokémon catalog. The
    # nightly Postgres sync (architecture §4) drops in behind the same CatalogIndex later.
    INMEMORY = "inmemory"
    TCGDEX = "tcgdex"


class PricingBackend(StrEnum):
    MOCK = "mock"
    TCGDEX = "tcgdex"
    # pokémontcg.io: native USD (TCGplayer) + EUR (Cardmarket), with a TCGdex EUR fallback.
    POKEMONTCG = "pokemontcg"


class GradingBackend(StrEnum):
    # Corners/edges/surface. ``inhouse`` is our owned classical-CV condition reader (no per-
    # scan vendor fee); ``mock`` is the deterministic fixture for tests. Centering is always
    # in-house and not selected here.
    MOCK = "mock"
    INHOUSE = "inhouse"


class AuthenticityBackend(StrEnum):
    # The visual-signal analyzer is built (not bought) per architecture §3.3. ``inhouse`` reads
    # the real capture pixels to judge, per signal, whether the capture can support that read
    # (driving the honest assess-vs-retake decision); the dispositive risk signal stays the
    # deterministic catalog-existence cross-check the service owns. ``mock`` is the test fixture.
    MOCK = "mock"
    INHOUSE = "inhouse"


class CaptureStorageBackend(StrEnum):
    # Where uploaded capture stills live. ``mock`` synthesises captures by reference (the
    # pre-grade tests' synthetic cards, no real bytes); ``memory`` and ``local`` keep real
    # uploaded bytes for dev (in process / on disk). The EU-region S3/GCS client drops in
    # behind the same CaptureStorage Protocol — residency stays an infra concern.
    MOCK = "mock"
    MEMORY = "memory"
    LOCAL = "local"


class DataLakeBackend(StrEnum):
    # The consented-capture training lake. ``mock`` (an in-memory recorder) is the only
    # backend wired today; the real EU-region writer drops in behind the same DataLakeSink
    # Protocol. Region residency stays an infra/compliance concern, not a call-site one.
    MOCK = "mock"


class AuthBackend(StrEnum):
    # ``session`` is the real bearer: an expiring, HMAC-signed token a password login issues
    # (the production default). ``dev_token`` is the forgeable-by-secret-holder dev/test bearer
    # the harness mints directly. Both verify behind the same AuthProvider seam.
    SESSION = "session"
    DEV_TOKEN = "dev_token"


class RateLimitBackend(StrEnum):
    MEMORY = "memory"
    REDIS = "redis"


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

    # Production defaults are the REAL providers: Holofy's own OCR recognizer resolving
    # against the live TCGdex catalog, TCGdex pricing, and the in-house condition grader.
    # Nothing here is a mock — the test suite pins mocks explicitly (see tests/conftest.py),
    # and a deployment can still override any one via its ``HOLOFY_*_PROVIDER`` env var.
    recognition_provider: RecognitionBackend = RecognitionBackend.INHOUSE
    # The catalog the in-house recognizer resolves reads against — the live TCGdex catalog
    # (keyless). ``inmemory`` is the seed catalog used by the offline smoke/tests only.
    catalog_provider: CatalogBackend = CatalogBackend.TCGDEX
    pricing_provider: PricingBackend = PricingBackend.TCGDEX
    grading_provider: GradingBackend = GradingBackend.INHOUSE
    authenticity_provider: AuthenticityBackend = AuthenticityBackend.INHOUSE

    # Where consented captures land as training examples (the moat, architecture §6). The
    # in-memory mock records emissions for tests; the real EU-region lake writer drops in
    # behind the same DataLakeSink Protocol with no change at the emission sites.
    datalake_sink: DataLakeBackend = DataLakeBackend.MOCK

    # Capture stills storage. Defaults to the synthetic-by-reference mock so the test suite
    # and keyless centering run with no bytes; ``memory``/``local`` keep real uploads for
    # dev (api-smoke uses memory). ``capture_storage_dir`` is only consulted for ``local``.
    # Real uploaded bytes, persisted to disk so a capture survives between the upload request
    # and the scan/pre-grade that reads it (and across a restart). The EU-region S3/GCS client
    # drops in behind the same Protocol for multi-instance; ``mock`` is the test-only synthetic.
    capture_storage: CaptureStorageBackend = CaptureStorageBackend.LOCAL
    capture_storage_dir: str = "./captures"
    # Ingress guards on the upload endpoint: a capture is a handful of stills, not an album,
    # and a phone still is a few MB — these cap storage COGS and reject obvious abuse before
    # any bytes are written.
    capture_max_images: int = 8
    capture_max_image_bytes: int = 12 * 1024 * 1024

    # Auth seam: the dev-token backend mints/verifies an HMAC-signed bearer that maps to a
    # seeded user, so endpoints are genuinely user-scoped with no OAuth/Clerk yet. Real
    # federated identity drops in behind the same AuthProvider Protocol (see ADR 0004).
    # Real bearer by default: a password login issues an expiring, HMAC-signed session token.
    # Tests pin ``dev_token`` (the harness mints subjects directly); the smokes do too.
    auth_provider: AuthBackend = AuthBackend.SESSION
    # Signs session/dev tokens. Required outside `local`; the default is dev-only and the
    # validator below refuses to boot a deployed environment that hasn't overridden it.
    auth_dev_secret: str = INSECURE_DEV_SECRET
    # How long an issued session token stays valid. 30 days balances "don't re-login daily"
    # against bounding a leaked token; a refresh-token rotation is a later refinement.
    session_token_ttl_seconds: int = 30 * 24 * 60 * 60

    # Brute-force throttle for /auth/login and /auth/register (short rolling window, per IP and
    # per email). Tight enough to stop credential stuffing, loose enough that a user mistyping
    # a password a few times isn't locked out.
    auth_throttle_window_seconds: int = 300
    auth_throttle_max_per_email: int = 8
    auth_throttle_max_per_ip: int = 30

    # Daily scan quota per account. The launch plan's freemium tier is 8/day (master plan §4),
    # but that's a *monetization* limit for paying-vs-free — during the free beta there's no
    # billing and near-zero per-scan cost (in-house OCR + open TCGdex), so this is a generous
    # abuse guard, not a paywall. Tighten it back to the tier limit when billing turns on.
    # Override per-env with HOLOFY_FREE_TIER_DAILY_SCANS.
    rate_limit_provider: RateLimitBackend = RateLimitBackend.MEMORY
    free_tier_daily_scans: int = 500
    # Only consulted when rate_limit_provider == redis — the shared counter store the whole
    # fleet's limiter reads/writes so the daily quota holds across instances.
    redis_url: str = "redis://localhost:6379/0"

    # Consulted when pricing_provider == pokemontcg. Native USD (TCGplayer) + EUR (Cardmarket) in
    # one source; falls back to TCGdex EUR for cards it doesn't carry. A free key (no charge) lifts
    # the rate limit and is sent when set; the API also serves modest volume keyless.
    pokemontcg_api_root: str = "https://api.pokemontcg.io/v2"
    pokemontcg_api_key: str | None = None
    pokemontcg_timeout_seconds: float = 10.0
    # TTL (seconds) for the in-memory pricing read-through cache fronting the network sources, so the
    # Vault's per-card pricing doesn't fan out to the upstream on every view. 12h: market guides move
    # daily, and the cache simply rewarms after a deploy. Misses are cached a quarter of this.
    pricing_cache_ttl_seconds: float = 43200.0

    # Only consulted when pricing_provider == tcgdex. No key required — TCGdex is open.
    tcgdex_api_root: str = "https://api.tcgdex.net/v2"
    tcgdex_locale: str = "en"  # primary locale, used for pricing lookups
    # Recognition searches each of these language catalogs and unions the hits, so a card
    # printed in any of them resolves by the name as it appears *on that card* (a French
    # "Dracaufeu" matches the fr catalog, an English "Charizard" the en catalog). English +
    # French cover the two largest communities and are both Latin-script the OCR reads today;
    # Japanese/Korean additionally need a CJK OCR model before adding their locales here.
    tcgdex_recognition_locales: list[str] = ["en", "fr"]
    tcgdex_timeout_seconds: float = 10.0

    # Artwork match index — the visual recognizer's database (perceptual hashes of catalog art,
    # built offline by scripts/build_image_index.py). When this file exists and is non-empty the
    # in-house recognizer matches a card by its picture first and uses OCR only to corroborate /
    # break reprint ties; when it's absent the recognizer transparently falls back to the
    # OCR-against-TCGdex text path, so the index is a data deployment, not a code switch.
    image_index_path: str = "./data/image_index.json"
    # Above this Hamming distance (over the 384-bit YCbCr hash) the nearest catalog artwork isn't
    # a real match — the card is outside the built index — so the recognizer defers to the text
    # path instead of asserting a far, wrong hit. Scaled 6× from the original 64-bit cutoff of 14.
    recognition_visual_max_distance: int = 84
    # The DINOv2 embedding model (ONNX), the primary recognition descriptor. Exported once by
    # scripts/export_recognition_model.py and deployed alongside the index (a data artefact, not
    # committed). When present, the recognizer matches by learned embedding first; when absent it
    # transparently falls back to the perceptual-hash index, then to the OCR/text path.
    recognition_model_path: str = "./data/recognition_model.onnx"
    # The catalog embedding matrix sidecar (float16 .npy, row-aligned to image_index_path). Defaults
    # to the index path with a .f16.npy suffix when blank.
    image_embeddings_path: str = ""
    # Below this cosine similarity the nearest catalog embedding isn't a real match — the card is
    # outside the built index — so the recognizer abstains to the hash/text tier rather than assert
    # a far, wrong hit. Calibrated against the real-capture eval set (distinct cards ~0.65, a true
    # match clears ~0.78).
    recognition_visual_min_similarity: float = 0.70

    # Below this top-1 confidence the scan flow must ask the user to confirm rather than
    # commit a guess — getting a high-value variant wrong is the product's worst failure.
    # Set between the two scoring bands so it splits them by *what was read*, not by photo
    # quality: a full "n/total" collector-number match pins one printing and scores ~0.83+
    # (commit), while a numerator-only or name-only read — the genuinely ambiguous cases ADR
    # 0002 guards — scores ~0.40–0.55 and routes to confirmation. At 0.85 even cleanly-read
    # cards were forced to confirm on every scan.
    recognition_confirm_threshold: float = 0.70
    # Below this top-1 confidence the read is too weak to be a real match at all: with the
    # Pokémon-only catalog, a non-Pokémon card (or an unreadable frame) produces at most a
    # spurious low-confidence candidate, which must reject cleanly as "unrecognized" rather
    # than commit it or offer a confirm against junk. This is the effective Pokémon gate.
    recognition_floor: float = 0.35

    # Pre-grade honesty floor (charter §3.1): if the centering measurement's confidence is
    # below this the capture is too poor to estimate a grade from, so the pre-grade refuses
    # with a "retake" signal rather than emitting a confident wrong range.
    #
    # Set conservatively (fail-closed): the 1-D border measurement was calibrated on flat,
    # clean-border captures, and on a casual angled phone photo of a real card it can latch
    # onto the artwork and read a *confident-but-wrong* ratio. Real-card validation
    # (2026-06-20) showed those bad reads land around 0.30–0.45 confidence, while a genuinely
    # flat, straight-on scan with a crisp border scores ~0.8+. A 0.6 floor refuses the former
    # and only grades the latter — better to ask for a cleaner scan than to show a wrong grade.
    # This stays high until the centering measurement is rebuilt to be robust to real art
    # (deskew + border detection that ignores interior edges).
    pregrade_min_centering_confidence: float = 0.6

    # Authenticity screening is only meaningful on cards worth faking (architecture §3.3:
    # "scoped to vintage/high-value"). Below this € value the service returns a typed
    # "not needed for this value" rather than a fake-precise risk score on a cheap common.
    authenticity_min_value_eur: float = 50.0

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
