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

import uuid

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    get_auth_throttle,
    get_capture_store,
    get_current_user,
    get_datalake_sink,
    get_email_sender,
    get_session,
    get_settings,
)
from app.auth.passwords import hash_password, verify_password
from app.auth.link_token import (
    check_fingerprint,
    fingerprint,
    issue_link_token,
    verify_link_token,
)
from app.auth.session_token import PROVIDER_NAME as SESSION_PROVIDER
from app.auth.session_token import issue_session_token
from app.auth.throttle import InMemoryAuthThrottle
from app.email.base import EmailMessage, EmailSender
from app.config import Settings
from app.core.errors import (
    ConstraintViolationError,
    InvalidCredentialError,
    QuotaExceededError,
)
from app.datalake.base import DataLakeSink
from app.db.erasure import plan_erasure
from app.db.models import User
from app.db.repositories import UserRepository
from app.grading.capture_store import CaptureStore
from app.schemas.auth import (
    AuthTokenResponse,
    AuthUser,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    ResetPasswordRequest,
    VerifyEmailRequest,
)
from app.schemas.datalake import TrainingExampleKind

router = APIRouter(prefix="/auth", tags=["auth"])


def _client_ip(request: Request) -> str:
    """The caller's IP for throttling. Behind the reverse proxy the real client is the first
    hop in X-Forwarded-For; fall back to the socket peer when there's no proxy."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _throttle_auth(
    request: Request, throttle: InMemoryAuthThrottle, settings: Settings, email: str
) -> None:
    """Short-window brute-force guard: cap attempts per IP and per target email. A breach is a
    typed 429, not a 401, so the client can show 'try again shortly'."""
    ip = _client_ip(request)
    window = settings.auth_throttle_window_seconds
    ip_ok = throttle.allow(f"ip:{ip}", limit=settings.auth_throttle_max_per_ip, window_seconds=window)
    email_ok = throttle.allow(
        f"email:{email}", limit=settings.auth_throttle_max_per_email, window_seconds=window
    )
    if not (ip_ok and email_ok):
        raise QuotaExceededError(
            "Too many attempts. Please wait a few minutes and try again.",
            details={"reset_seconds": window},
        )


@router.post(
    "/register",
    response_model=AuthTokenResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    request: RegisterRequest,
    http_request: Request,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    throttle: InMemoryAuthThrottle = Depends(get_auth_throttle),
) -> AuthTokenResponse:
    _throttle_auth(http_request, throttle, settings, request.email)
    users = UserRepository(session)
    # Friendly, explicit duplicate message; the unique constraint is still the race backstop
    # (a concurrent register of the same email surfaces as a 409 from the repository's flush).
    if await users.get_by_email(request.email) is not None:
        raise ConstraintViolationError(
            "An account with this email already exists. Try logging in instead.",
            details={"field": "email"},
        )
    # The session subject is a fresh opaque id, NOT the email — so a token issued to one
    # account can never resolve to a *different* account that later registers the same email
    # (e.g. after this one is deleted). The email stays the login handle for password lookup.
    user = await users.create(
        auth_provider=SESSION_PROVIDER,
        auth_subject=uuid.uuid4().hex,
        email=request.email,
        password_hash=hash_password(request.password),
    )
    return _token_response(user, settings)


@router.post("/login", response_model=AuthTokenResponse)
async def login(
    request: LoginRequest,
    http_request: Request,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    throttle: InMemoryAuthThrottle = Depends(get_auth_throttle),
) -> AuthTokenResponse:
    _throttle_auth(http_request, throttle, settings, request.email)
    user = await UserRepository(session).get_by_email(request.email)
    # One indistinguishable failure for "no such account" and "wrong password" — no account
    # enumeration. ``verify_password`` is still run on a dummy hash? Not needed here: the
    # constant-time compare inside it covers the present-account case; the absent-account case
    # is rare and the timing difference doesn't leak a usable signal at this granularity.
    if user is None or user.password_hash is None or not verify_password(
        request.password, user.password_hash
    ):
        raise InvalidCredentialError("Email or password is incorrect.")
    # A correct login clears the throttle so earlier typos don't count against this account/IP.
    throttle.reset(f"email:{request.email}")
    throttle.reset(f"ip:{_client_ip(http_request)}")
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


_RESET_PURPOSE = "password_reset"
_VERIFY_PURPOSE = "email_verify"
# A neutral acknowledgement the forgot-password endpoint always returns, whether or not the email
# has an account — so the endpoint can't be used to discover which emails are registered.
_FORGOT_ACK = "If an account exists for that email, a reset link is on its way."


def _reset_fp(user: User) -> str:
    # Bind the reset token to the current password hash: once the password changes, the link dies.
    return fingerprint(_RESET_PURPOSE, str(user.password_hash))


@router.post("/password/forgot", response_model=MessageResponse, status_code=status.HTTP_202_ACCEPTED)
async def forgot_password(
    request: ForgotPasswordRequest,
    http_request: Request,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    throttle: InMemoryAuthThrottle = Depends(get_auth_throttle),
    email_sender: EmailSender = Depends(get_email_sender),
) -> MessageResponse:
    """Start a password reset. The response is identical whether or not the email has an account
    (no enumeration); a real account is emailed a signed, one-hour, single-use link."""
    _throttle_auth(http_request, throttle, settings, request.email)
    user = await UserRepository(session).get_by_email(request.email)
    if user is not None and user.password_hash is not None:
        token = issue_link_token(
            str(user.auth_subject),
            purpose=_RESET_PURPOSE,
            secret=settings.auth_dev_secret,
            ttl_seconds=settings.password_reset_ttl_seconds,
            fp=_reset_fp(user),
        )
        link = f"{settings.app_base_url}/auth/reset?token={token}"
        await email_sender.send(
            EmailMessage(
                to=request.email,
                subject="Reset your Holofy password",
                body=(
                    "We received a request to reset your Holofy password.\n\n"
                    f"Reset it here (valid for 1 hour): {link}\n\n"
                    "If you didn't ask for this, you can ignore this email — your password is unchanged."
                ),
            )
        )
    return MessageResponse(detail=_FORGOT_ACK)


@router.post("/password/reset", response_model=AuthTokenResponse)
async def reset_password(
    request: ResetPasswordRequest,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> AuthTokenResponse:
    """Complete a reset with the emailed token: set the new password (which revokes every existing
    session) and sign the user back in. A bad/expired/already-used token is a single 401."""
    users = UserRepository(session)
    user = await _user_for_link(users, request.token, purpose=_RESET_PURPOSE, settings=settings, fp_for=_reset_fp)
    await users.set_password(user, password_hash=hash_password(request.password))
    return _token_response(user, settings)


@router.post("/email/verify/request", response_model=MessageResponse, status_code=status.HTTP_202_ACCEPTED)
async def request_email_verification(
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    email_sender: EmailSender = Depends(get_email_sender),
) -> MessageResponse:
    """Email the signed-in account a verification link (no-op acknowledgement if already verified
    or the account carries no email)."""
    if user.email and user.email_verified_at is None:
        token = issue_link_token(
            str(user.auth_subject),
            purpose=_VERIFY_PURPOSE,
            secret=settings.auth_dev_secret,
            ttl_seconds=settings.email_verify_ttl_seconds,
            fp=fingerprint(_VERIFY_PURPOSE, user.email),
        )
        link = f"{settings.app_base_url}/auth/verify?token={token}"
        await email_sender.send(
            EmailMessage(
                to=user.email,
                subject="Confirm your Holofy email",
                body=f"Confirm your email to finish setting up Holofy: {link}\n\n(Valid for 24 hours.)",
            )
        )
    return MessageResponse(detail="If your email needs confirming, a link is on its way.")


@router.post("/email/verify", response_model=AuthUser)
async def verify_email(
    request: VerifyEmailRequest,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> AuthUser:
    """Confirm an email with the emailed token. The fingerprint binds the token to that email, so a
    later email change invalidates an outstanding link."""
    users = UserRepository(session)
    user = await _user_for_link(
        users, request.token, purpose=_VERIFY_PURPOSE, settings=settings,
        fp_for=lambda u: fingerprint(_VERIFY_PURPOSE, u.email or ""),
    )
    await users.mark_email_verified(user)
    return AuthUser(id=str(user.id), email=user.email or "")


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def logout_all(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Sign the account out on every device — every token issued before now stops working."""
    await UserRepository(session).revoke_sessions(user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _user_for_link(
    users: UserRepository, token: str, *, purpose: str, settings: Settings, fp_for
) -> User:
    """Resolve the account a link token names, verifying purpose + expiry + signature, then the
    fingerprint (which makes the link single-use). Any failure is one indistinguishable 401."""
    invalid = InvalidCredentialError("This link is invalid or has expired.")
    try:
        subject, token_fp = verify_link_token(
            token, purpose=purpose, secret=settings.auth_dev_secret
        )
    except InvalidCredentialError:
        raise invalid from None
    user = await users.get_by_auth(SESSION_PROVIDER, subject)
    # Recompute the fingerprint from the *current* account state and compare: a token minted against
    # an older password hash / email no longer matches, so a used or stale link is rejected.
    if user is None or not check_fingerprint(token_fp, fp_for(user)):
        raise invalid
    return user


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
