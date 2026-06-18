"""FastAPI dependency providers.

The long-lived collaborators (providers, auth, rate limiter, the session factory) are built
once at startup (see ``app.main`` lifespan) and stashed on ``app.state``; these accessors
hand them to routes. Per-request things — a database session, the resolved ``User``, the
stateless ``ScanService`` — are assembled here from those singletons.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.base import AuthProvider
from app.authenticity.reference_catalog import ReferenceCatalogExistenceChecker
from app.config import Settings
from app.core.errors import NotAuthenticatedError
from app.datalake.base import DataLakeSink
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
from app.services.collection import CollectionService
from app.services.portfolio import PortfolioService
from app.services.pregrade import PregradeService
from app.services.scan import ScanService

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


def get_datalake_sink(request: Request) -> DataLakeSink:
    return request.app.state.datalake_sink


def get_auth_provider(request: Request) -> AuthProvider:
    return request.app.state.auth_provider


def get_rate_limiter(request: Request) -> RateLimiter:
    return request.app.state.rate_limiter


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
    """Resolve the bearer token to the persisted ``User``, provisioning on first sight.

    The token's identity is verified by the ``AuthProvider``; the user row is found-or-created
    on its ``(provider, subject)`` pair, so a freshly issued token scopes to a stable user
    without a separate signup call. A missing token is a 401, distinct from an invalid one.
    """
    if credentials is None or not credentials.credentials:
        raise NotAuthenticatedError("Authentication is required for this endpoint.")

    identity = auth.authenticate(credentials.credentials)
    users = UserRepository(session)
    user = await users.get_by_auth(identity.provider, identity.subject)
    if user is None:
        user = await users.create(
            auth_provider=identity.provider, auth_subject=identity.subject
        )
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
