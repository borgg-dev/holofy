"""FastAPI dependency providers.

The long-lived collaborators (providers, auth, rate limiter, the session factory) are built
once at startup (see ``app.main`` lifespan) and stashed on ``app.state``; these accessors
hand them to routes. Per-request things — a database session, the resolved ``User``, the
stateless ``ScanService`` — are assembled here from those singletons.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import timezone

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.base import AuthProvider
from app.auth.session_token import PROVIDER_NAME as SESSION_PROVIDER
from app.auth.throttle import InMemoryAuthThrottle
from app.authenticity.reference_catalog import ReferenceCatalogExistenceChecker
from app.config import Settings
from app.core.errors import (
    CaptureUploadUnavailableError,
    InvalidCredentialError,
    NotAuthenticatedError,
)
from app.datalake.base import DataLakeSink
from app.email.base import EmailSender
from app.db.models import User
from app.db.repositories import (
    CardRepository,
    CollectionRepository,
    PortfolioRepository,
    UserRepository,
)
from app.grading.capture_store import CaptureStore
from app.providers.base import (
    AuthenticityProvider,
    GradingProvider,
    PricingProvider,
    RecognitionProvider,
)
from app.ratelimit.base import RateLimiter
from app.services.authenticity import AuthenticityService
from app.services.batch_scan import BatchScanService
from app.services.collection import CollectionService
from app.services.portfolio import PortfolioService
from app.services.pregrade import PregradeService
from app.services.scan import ScanService
from app.storage.base import CaptureStorage

# The single daily scan budget both ``/scan`` and ``/scan/batch`` charge against, so a batch
# can't be used to sidestep the per-user free-tier limit (master plan §4).
SCAN_QUOTA_KEY = "scan:{user_id}"

# auto_error off: a missing/blank Authorization header must surface as our own envelope,
# not Starlette's default 403, so the client parses every auth failure the same way.
_bearer_scheme = HTTPBearer(auto_error=False)


def get_settings(request: Request) -> Settings:
    """The settings the app was built with — read from state, not the module cache, so a
    test that constructs an app with overridden settings sees them everywhere.
    """
    return request.app.state.settings


def get_recognition_provider(request: Request) -> RecognitionProvider:
    return request.app.state.recognition_provider


def get_pricing_provider(request: Request) -> PricingProvider:
    return request.app.state.pricing_provider


def get_grading_provider(request: Request) -> GradingProvider:
    return request.app.state.grading_provider


def get_authenticity_provider(request: Request) -> AuthenticityProvider:
    return request.app.state.authenticity_provider


def get_capture_store(request: Request) -> CaptureStore:
    return request.app.state.capture_store


def get_email_sender(request: Request) -> "EmailSender":
    return request.app.state.email_sender


def get_capture_storage(request: Request) -> CaptureStorage:
    """The capture store, but only when it can accept uploads.

    The synthetic mock satisfies the read-only ``CaptureStore`` (it conjures captures by
    reference) but has no ``save`` — uploading against it is meaningless. The structural
    check turns that misconfiguration into a clear 503 at the upload edge rather than an
    ``AttributeError`` deeper in.
    """
    store = request.app.state.capture_store
    if not isinstance(store, CaptureStorage):
        raise CaptureUploadUnavailableError(
            "Capture upload is unavailable with the current storage backend."
        )
    return store


def get_datalake_sink(request: Request) -> DataLakeSink:
    return request.app.state.datalake_sink


def get_auth_provider(request: Request) -> AuthProvider:
    return request.app.state.auth_provider


def get_rate_limiter(request: Request) -> RateLimiter:
    return request.app.state.rate_limiter


def get_auth_throttle(request: Request) -> "InMemoryAuthThrottle":
    return request.app.state.auth_throttle


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """A request-scoped unit of work: commits on success, rolls back on any error.

    Routes and the services they call share this one session, so a scan that both logs a
    ``ScanRecord`` and touches the collection is one atomic transaction.
    """
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    auth: AuthProvider = Depends(get_auth_provider),
    session: AsyncSession = Depends(get_session),
) -> User:
    """Resolve the bearer token to the persisted ``User``.

    The token's identity is verified by the ``AuthProvider``; the user row is keyed on its
    ``(provider, subject)`` pair. A **session** account must already exist (it's created at
    register), so a session token for a missing user — e.g. a token still in hand after the
    account was deleted — is a 401, never a silently resurrected blank account. Other backends
    (the dev token) provision on first sight, so the harness can mint a subject and use it
    without a separate signup. A missing token is a 401, distinct from an invalid one.
    """
    if credentials is None or not credentials.credentials:
        raise NotAuthenticatedError("Authentication is required for this endpoint.")

    identity = auth.authenticate(credentials.credentials)
    users = UserRepository(session)
    user = await users.get_by_auth(identity.provider, identity.subject)
    if user is None:
        if identity.provider == SESSION_PROVIDER:
            raise InvalidCredentialError(
                "This account no longer exists or the session is no longer valid."
            )
        user = await users.create(
            auth_provider=identity.provider, auth_subject=identity.subject
        )
    # Session revocation: a token issued before the account's session epoch (a password reset or an
    # explicit log-out-everywhere bumps it) is rejected even though its signature/expiry are valid.
    # The stored instant is UTC, but SQLite hands it back tz-naive — treat a naive value as UTC so
    # the epoch comparison can't skew by the host's local offset.
    epoch = user.sessions_valid_from
    if epoch is not None and identity.issued_at is not None:
        if epoch.tzinfo is None:
            epoch = epoch.replace(tzinfo=timezone.utc)
        if identity.issued_at < epoch.timestamp():
            raise InvalidCredentialError("This session has been signed out. Please log in again.")
    return user


def get_scan_service(
    settings: Settings = Depends(get_settings),
    recognition: RecognitionProvider = Depends(get_recognition_provider),
    pricing: PricingProvider = Depends(get_pricing_provider),
    data_lake: DataLakeSink = Depends(get_datalake_sink),
) -> ScanService:
    return ScanService(
        recognition=recognition,
        pricing=pricing,
        data_lake=data_lake,
        confirm_threshold=settings.recognition_confirm_threshold,
        recognition_floor=settings.recognition_floor,
    )


def get_batch_scan_service(
    user: User = Depends(get_current_user),
    scan_service: ScanService = Depends(get_scan_service),
    data_lake: DataLakeSink = Depends(get_datalake_sink),
    limiter: RateLimiter = Depends(get_rate_limiter),
    settings: Settings = Depends(get_settings),
) -> BatchScanService:
    # Reuses the single-scan ``classify`` path for recognize+price; the batch service adds only
    # dedupe, per-card quota and per-card persistence on top. The quota key is the *same* one
    # ``/scan`` charges, so the two endpoints share one daily free-tier budget per user.
    return BatchScanService(
        scan_service=scan_service,
        data_lake=data_lake,
        limiter=limiter,
        quota_key=SCAN_QUOTA_KEY.format(user_id=user.id),
        daily_limit=settings.free_tier_daily_scans,
    )


def get_pregrade_service(
    settings: Settings = Depends(get_settings),
    grading: GradingProvider = Depends(get_grading_provider),
) -> PregradeService:
    return PregradeService(
        grading=grading,
        min_centering_confidence=settings.pregrade_min_centering_confidence,
    )


def get_authenticity_service(
    settings: Settings = Depends(get_settings),
    provider: AuthenticityProvider = Depends(get_authenticity_provider),
) -> AuthenticityService:
    # The catalog-existence checker is stateless and deterministic, so it is built per
    # request rather than held on app state; the reference-DB-backed one drops in here later.
    return AuthenticityService(
        provider=provider,
        catalog=ReferenceCatalogExistenceChecker(),
        min_value_eur=settings.authenticity_min_value_eur,
    )


def get_collection_service(
    session: AsyncSession = Depends(get_session),
    pricing: PricingProvider = Depends(get_pricing_provider),
) -> CollectionService:
    return CollectionService(
        cards=CardRepository(session),
        collection=CollectionRepository(session),
        pricing=pricing,
    )


def get_portfolio_service(
    session: AsyncSession = Depends(get_session),
    collection: CollectionService = Depends(get_collection_service),
) -> PortfolioService:
    return PortfolioService(
        collection=collection,
        portfolio=PortfolioRepository(session),
    )
