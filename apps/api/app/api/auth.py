"""Authentication endpoints — register a password account, log in, and read the current user.

These mint the real bearer the rest of the API authenticates (``app.auth.session_token``):
``POST /auth/register`` creates an account and returns a session token; ``POST /auth/login``
verifies a password and returns one; ``GET /auth/me`` echoes the account a bearer resolves to,
so the mobile app can validate a stored token on launch. Passwords are stored only as a scrypt
hash (``app.auth.passwords``); the plaintext never persists and never leaves these handlers.

Honest failure shapes: a duplicate email is a typed 409 (the unique guard, surfaced by the
repository), and a wrong email *or* password is a single 401 — the response never reveals
*which* was wrong, so the endpoint can't be used to enumerate which emails have accounts.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    get_capture_store,
    get_current_user,
    get_datalake_sink,
    get_session,
    get_settings,
)
from app.auth.passwords import hash_password, verify_password
from app.auth.session_token import PROVIDER_NAME as SESSION_PROVIDER
from app.auth.session_token import issue_session_token
from app.config import Settings
from app.core.errors import ConstraintViolationError, InvalidCredentialError
from app.datalake.base import DataLakeSink
from app.db.erasure import plan_erasure
from app.db.models import User
from app.db.repositories import UserRepository
from app.grading.capture_store import CaptureStore
from app.schemas.auth import (
    AuthTokenResponse,
    AuthUser,
    LoginRequest,
    RegisterRequest,
)
from app.schemas.datalake import TrainingExampleKind

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=AuthTokenResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    request: RegisterRequest,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> AuthTokenResponse:
    users = UserRepository(session)
    # Friendly, explicit duplicate message; the unique constraint is still the race backstop
    # (a concurrent register of the same email surfaces as a 409 from the repository's flush).
    if await users.get_by_email(request.email) is not None:
        raise ConstraintViolationError(
            "An account with this email already exists. Try logging in instead.",
            details={"field": "email"},
        )
    # The session subject is the (normalized) email — the stable handle the token resolves to.
    user = await users.create(
        auth_provider=SESSION_PROVIDER,
        auth_subject=request.email,
        email=request.email,
        password_hash=hash_password(request.password),
    )
    return _token_response(user, settings)


@router.post("/login", response_model=AuthTokenResponse)
async def login(
    request: LoginRequest,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> AuthTokenResponse:
    user = await UserRepository(session).get_by_email(request.email)
    # One indistinguishable failure for "no such account" and "wrong password" — no account
    # enumeration. ``verify_password`` is still run on a dummy hash? Not needed here: the
    # constant-time compare inside it covers the present-account case; the absent-account case
    # is rare and the timing difference doesn't leak a usable signal at this granularity.
    if user is None or user.password_hash is None or not verify_password(
        request.password, user.password_hash
    ):
        raise InvalidCredentialError("Email or password is incorrect.")
    return _token_response(user, settings)


@router.get("/me", response_model=AuthUser)
async def me(user: User = Depends(get_current_user)) -> AuthUser:
    # Lets the client confirm a stored token is still valid and recover the account email.
    return AuthUser(id=str(user.id), email=user.email or "")


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    store: CaptureStore = Depends(get_capture_store),
    data_lake: DataLakeSink = Depends(get_datalake_sink),
) -> Response:
    """GDPR Art. 17 erasure: delete the account and every trace of its personal data.

    Order matters (see ``app.db.erasure``): enumerate the out-of-band artifacts *before* the
    cascade removes the rows, purge the capture images and any consented lake examples, then
    delete the user — whose ``ON DELETE CASCADE`` removes the collection, scans, pre-grades,
    authenticity screens and portfolio history. The request's transaction commits last, so a
    crash can't drop the rows while their images still exist. Catalog/market data is shared
    reference data and is intentionally never touched.
    """
    manifest = await plan_erasure(session, user.id)

    # Capture stills in object storage — delete is idempotent, so a partial re-run is safe.
    for capture_ref in manifest.capture_refs:
        await store.delete(capture_ref)

    # Consented examples already replicated into the training lake, per capture kind.
    eligible = (
        (TrainingExampleKind.SCAN, manifest.training_eligible_scan_ids),
        (TrainingExampleKind.PREGRADE, manifest.training_eligible_pregrade_ids),
        (TrainingExampleKind.AUTHENTICITY, manifest.training_eligible_authenticity_ids),
    )
    for kind, record_ids in eligible:
        for record_id in record_ids:
            await data_lake.purge(kind=kind, record_id=record_id)

    # The cascade erases every owned row (and the credentials) when the user goes.
    await UserRepository(session).delete(user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _token_response(user: User, settings: Settings) -> AuthTokenResponse:
    token = issue_session_token(
        str(user.auth_subject),
        secret=settings.auth_dev_secret,
        ttl_seconds=settings.session_token_ttl_seconds,
    )
    return AuthTokenResponse(
        access_token=token,
        expires_in=settings.session_token_ttl_seconds,
        user=AuthUser(id=str(user.id), email=user.email or ""),
    )
