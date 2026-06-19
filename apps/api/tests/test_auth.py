"""Real authentication coverage: register/login issue a working session bearer, and the
password/session primitives behave (hash roundtrip, signature + expiry verification).

The shipped app authenticates with the session-token backend, so these tests build a client on
``AuthBackend.SESSION`` (the conftest ``client`` pins dev_token for the rest of the suite) and
drive the actual HTTP endpoints — register → use the token on a scoped endpoint → login again.
"""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from app.auth.passwords import hash_password, verify_password
from app.auth.session_token import SessionTokenAuthProvider, issue_session_token
from app.config import (
    AuthBackend,
    AuthenticityBackend,
    CaptureStorageBackend,
    CatalogBackend,
    DataLakeBackend,
    GradingBackend,
    PricingBackend,
    RateLimitBackend,
    RecognitionBackend,
    Settings,
)
from app.core.errors import InvalidCredentialError
from app.db.base import Base
from app.main import create_app

_SECRET = "session-test-secret"


@pytest.fixture
def auth_client():
    settings = Settings(
        auth_provider=AuthBackend.SESSION,
        auth_dev_secret=_SECRET,
        recognition_provider=RecognitionBackend.MOCK,
        catalog_provider=CatalogBackend.INMEMORY,
        pricing_provider=PricingBackend.MOCK,
        grading_provider=GradingBackend.MOCK,
        authenticity_provider=AuthenticityBackend.MOCK,
        capture_storage=CaptureStorageBackend.MOCK,
        datalake_sink=DataLakeBackend.MOCK,
        rate_limit_provider=RateLimitBackend.MEMORY,
        database_url="sqlite+aiosqlite://",
        log_json=False,
        cors_allow_origins=["https://app.holofy.test"],
    )
    with TestClient(create_app(settings)) as client:
        engine = client.app.state.db_engine

        async def _create_schema() -> None:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

        client.portal.call(_create_schema)
        yield client


def _register(client, email="collector@example.com", password="hunter2pass"):  # noqa: ANN001
    return client.post("/auth/register", json={"email": email, "password": password})


def test_register_issues_a_working_bearer(auth_client) -> None:  # noqa: ANN001
    res = _register(auth_client)
    assert res.status_code == 201
    body = res.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0
    assert body["user"]["email"] == "collector@example.com"

    # The issued token authorizes a user-scoped endpoint (fresh account → empty portfolio).
    token = body["access_token"]
    me = auth_client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200 and me.json()["email"] == "collector@example.com"
    pf = auth_client.get("/portfolio", headers={"Authorization": f"Bearer {token}"})
    assert pf.status_code == 200


def test_email_is_normalized_and_duplicate_is_a_conflict(auth_client) -> None:  # noqa: ANN001
    assert _register(auth_client, email="Collector@Example.com  ").status_code == 201
    # Same address, different casing/whitespace → the unique account, a typed 409.
    dup = _register(auth_client, email="collector@example.com")
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "constraint_violation"


def test_login_succeeds_with_correct_password_and_scopes_to_same_user(auth_client) -> None:  # noqa: ANN001
    reg = _register(auth_client).json()
    login = auth_client.post(
        "/auth/login",
        json={"email": "collector@example.com", "password": "hunter2pass"},
    )
    assert login.status_code == 200
    # Same account both times — the login token resolves to the registered user's id.
    assert login.json()["user"]["id"] == reg["user"]["id"]


def test_login_rejects_wrong_password_and_unknown_email_identically(auth_client) -> None:  # noqa: ANN001
    _register(auth_client)
    wrong = auth_client.post(
        "/auth/login",
        json={"email": "collector@example.com", "password": "not-the-password"},
    )
    missing = auth_client.post(
        "/auth/login",
        json={"email": "nobody@example.com", "password": "whatever123"},
    )
    assert wrong.status_code == 401 and missing.status_code == 401
    # Indistinguishable message → no account enumeration.
    assert wrong.json()["error"]["message"] == missing.json()["error"]["message"]


def test_garbage_and_short_inputs_are_rejected(auth_client) -> None:  # noqa: ANN001
    assert auth_client.post("/auth/register", json={"email": "not-an-email", "password": "longenough"}).status_code == 422
    assert auth_client.post("/auth/register", json={"email": "a@b.co", "password": "short"}).status_code == 422


def test_unscoped_endpoint_rejects_a_dev_token_under_session_backend(auth_client) -> None:  # noqa: ANN001
    # A forged/dev token must not authenticate when the app runs on the session backend.
    from app.auth.dev_token import mint_dev_token

    forged = mint_dev_token("intruder", secret=_SECRET)
    res = auth_client.get("/auth/me", headers={"Authorization": f"Bearer {forged}"})
    assert res.status_code == 401


# ── Unit-level: the primitives ────────────────────────────────────────────────


def test_password_hash_roundtrips_and_rejects_wrong() -> None:
    stored = hash_password("correct horse battery staple")
    assert stored.startswith("scrypt$")
    assert "correct horse" not in stored  # never plaintext
    assert verify_password("correct horse battery staple", stored)
    assert not verify_password("wrong", stored)
    assert not verify_password("x", "garbage$not$a$valid$hash$value")


def test_session_token_verifies_and_expires() -> None:
    provider = SessionTokenAuthProvider(secret=_SECRET)
    token = issue_session_token("user@example.com", secret=_SECRET, ttl_seconds=60)
    identity = provider.authenticate(token)
    assert identity.provider == "session" and identity.subject == "user@example.com"

    # Wrong secret → does not verify.
    with pytest.raises(InvalidCredentialError):
        SessionTokenAuthProvider(secret="other").authenticate(token)

    # Already expired → rejected.
    expired = issue_session_token("user@example.com", secret=_SECRET, ttl_seconds=-1)
    with pytest.raises(InvalidCredentialError):
        provider.authenticate(expired)

    # Tampered payload → signature fails.
    payload, _, sig = token.partition(".")
    with pytest.raises(InvalidCredentialError):
        provider.authenticate(f"{payload}x.{sig}")


def test_issued_token_carries_the_configured_ttl() -> None:
    token = issue_session_token("u", secret=_SECRET, ttl_seconds=120)
    # Decode the exp without the provider to assert the TTL window.
    import base64
    import json

    payload_b64 = token.split(".")[0]
    payload = json.loads(base64.urlsafe_b64decode(payload_b64 + "=" * (-len(payload_b64) % 4)))
    assert 100 <= payload["exp"] - int(time.time()) <= 121
