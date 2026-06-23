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


def test_delete_account_erases_data_and_kills_the_token(auth_client) -> None:  # noqa: ANN001
    token = _register(auth_client).json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}

    # Build some personal data: a scan lands a card in the catalog, then add it to the vault.
    scan = auth_client.post("/scan", json={"bundle_id": "mock-high-confidence"}, headers=auth)
    cid = scan.json()["card"]["identity"]["canonical_id"]
    auth_client.post("/collection", json={"canonical_id": cid}, headers=auth)
    assert len(auth_client.get("/collection", headers=auth).json()) == 1

    # Erase the account.
    assert auth_client.delete("/auth/me", headers=auth).status_code == 204

    # The still-valid token must not resurrect a blank account — it's now a 401, not a new user.
    assert auth_client.get("/auth/me", headers=auth).status_code == 401
    assert auth_client.get("/collection", headers=auth).status_code == 401
    # The login no longer works (credentials erased).
    relogin = auth_client.post(
        "/auth/login", json={"email": "collector@example.com", "password": "hunter2pass"}
    )
    assert relogin.status_code == 401
    # …and the email is freed for a fresh, empty account.
    fresh = _register(auth_client)
    assert fresh.status_code == 201
    fresh_auth = {"Authorization": f"Bearer {fresh.json()['access_token']}"}
    assert auth_client.get("/collection", headers=fresh_auth).json() == []


def test_delete_account_requires_authentication(auth_client) -> None:  # noqa: ANN001
    assert auth_client.delete("/auth/me").status_code == 401


def test_login_is_rate_limited_after_repeated_failures(auth_client) -> None:  # noqa: ANN001
    _register(auth_client)
    statuses = []
    for _ in range(15):
        r = auth_client.post(
            "/auth/login",
            json={"email": "collector@example.com", "password": "wrong-password"},
        )
        statuses.append(r.status_code)
    # The first wrong attempts are 401 (bad creds); once the short-window cap is hit the
    # endpoint throttles with 429 instead of letting an attacker keep guessing.
    assert 401 in statuses
    assert 429 in statuses
    assert statuses[-1] == 429


def test_session_token_subject_is_opaque_not_the_email(auth_client) -> None:  # noqa: ANN001
    # The token subject must not be the email, so a token can never resolve to a different
    # account that later registers the same address.
    import base64
    import json

    token = _register(auth_client).json()["access_token"]
    payload_b64 = token.split(".")[0]
    payload = json.loads(base64.urlsafe_b64decode(payload_b64 + "=" * (-len(payload_b64) % 4)))
    assert payload["sub"] != "collector@example.com"
    assert "@" not in payload["sub"]


# ── Password reset, email verification, session revocation ────────────────────


def _link_token(client) -> str:  # noqa: ANN001
    """Pull the token out of the link in the last (logged) email."""
    msg = client.app.state.email_sender.last_message
    assert msg is not None, "expected an email to have been sent"
    return msg.body.split("token=")[1].split()[0].strip()


def test_password_reset_full_flow(auth_client) -> None:  # noqa: ANN001
    _register(auth_client, password="originalpass1")
    # Request a reset — neutral 202 ack, an email is sent for the real account.
    ack = auth_client.post("/auth/password/forgot", json={"email": "collector@example.com"})
    assert ack.status_code == 202
    token = _link_token(auth_client)

    # Complete the reset → signs the user back in with a working bearer.
    res = auth_client.post("/auth/password/reset", json={"token": token, "password": "brandnewpass2"})
    assert res.status_code == 200
    new_token = res.json()["access_token"]
    assert auth_client.get("/auth/me", headers={"Authorization": f"Bearer {new_token}"}).status_code == 200

    # The new password logs in; the old one no longer does.
    assert auth_client.post("/auth/login", json={"email": "collector@example.com", "password": "brandnewpass2"}).status_code == 200
    assert auth_client.post("/auth/login", json={"email": "collector@example.com", "password": "originalpass1"}).status_code == 401


def test_forgot_password_does_not_enumerate(auth_client) -> None:  # noqa: ANN001
    _register(auth_client)
    auth_client.app.state.email_sender.last_message = None
    # An unknown email gets the same 202 ack — and crucially, no email is sent.
    res = auth_client.post("/auth/password/forgot", json={"email": "nobody@example.com"})
    assert res.status_code == 202
    assert auth_client.app.state.email_sender.last_message is None
    # The real account's ack body is identical.
    known = auth_client.post("/auth/password/forgot", json={"email": "collector@example.com"})
    assert known.json()["detail"] == res.json()["detail"]


def test_reset_revokes_existing_sessions(auth_client) -> None:  # noqa: ANN001
    old_token = _register(auth_client, password="originalpass1").json()["access_token"]
    auth = {"Authorization": f"Bearer {old_token}"}
    assert auth_client.get("/auth/me", headers=auth).status_code == 200  # valid before reset

    auth_client.post("/auth/password/forgot", json={"email": "collector@example.com"})
    token = _link_token(auth_client)
    assert auth_client.post("/auth/password/reset", json={"token": token, "password": "brandnewpass2"}).status_code == 200

    # The pre-reset session is now revoked even though its signature/expiry are still valid.
    assert auth_client.get("/auth/me", headers=auth).status_code == 401


def test_reset_token_is_single_use(auth_client) -> None:  # noqa: ANN001
    _register(auth_client, password="originalpass1")
    auth_client.post("/auth/password/forgot", json={"email": "collector@example.com"})
    token = _link_token(auth_client)
    assert auth_client.post("/auth/password/reset", json={"token": token, "password": "brandnewpass2"}).status_code == 200
    # Re-using the link after the password changed fails (the fingerprint no longer matches).
    again = auth_client.post("/auth/password/reset", json={"token": token, "password": "thirdpass33"})
    assert again.status_code == 401


def test_reset_rejects_a_garbage_token(auth_client) -> None:  # noqa: ANN001
    _register(auth_client)
    assert auth_client.post("/auth/password/reset", json={"token": "not.a.token", "password": "whatever123"}).status_code == 401


def test_email_verification_flow(auth_client) -> None:  # noqa: ANN001
    token = _register(auth_client).json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}
    assert auth_client.post("/auth/email/verify/request", headers=auth).status_code == 202
    verify_token = _link_token(auth_client)
    res = auth_client.post("/auth/email/verify", json={"token": verify_token})
    assert res.status_code == 200 and res.json()["email"] == "collector@example.com"
    # A reset token can't be replayed as a verification (purpose mismatch).
    auth_client.post("/auth/password/forgot", json={"email": "collector@example.com"})
    reset_token = _link_token(auth_client)
    assert auth_client.post("/auth/email/verify", json={"token": reset_token}).status_code == 401


def test_logout_all_revokes_every_session(auth_client) -> None:  # noqa: ANN001
    token = _register(auth_client).json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}
    assert auth_client.get("/auth/me", headers=auth).status_code == 200
    assert auth_client.post("/auth/logout-all", headers=auth).status_code == 204
    # The token used to make the request is itself now invalid.
    assert auth_client.get("/auth/me", headers=auth).status_code == 401


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
