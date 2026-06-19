"""API-level coverage via FastAPI's TestClient — health, auth, the two scan outcomes, the
error envelope, and the request-id round-trip. Runs entirely on mock providers against an
in-memory database.
"""

from __future__ import annotations

from app.schemas.scan import ScanOutcome
from tests.conftest import auth_header


def test_health_reports_active_backends_and_region(client) -> None:  # noqa: ANN001
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["recognition_provider"] == "mock"
    assert body["pricing_provider"] == "mock"
    assert body["data_region"].startswith("eu-")


def test_scan_requires_authentication(client) -> None:  # noqa: ANN001
    response = client.post("/scan", json={"bundle_id": "mock-high-confidence"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


def test_scan_rejects_forged_token(client) -> None:  # noqa: ANN001
    response = client.post(
        "/scan",
        json={"bundle_id": "mock-high-confidence"},
        headers={"Authorization": "Bearer collector-1.deadbeef"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credential"


def test_scan_resolves_high_confidence_bundle(client) -> None:  # noqa: ANN001
    response = client.post(
        "/scan", json={"bundle_id": "mock-high-confidence"}, headers=auth_header()
    )

    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == ScanOutcome.RESOLVED
    assert body["card"]["identity"]["canonical_id"] == "origins-8"
    assert body["card"]["price"]["currency"] == "EUR"
    assert body["choices"] is None


def test_scan_low_confidence_bundle_requests_confirmation(client) -> None:  # noqa: ANN001
    response = client.post(
        "/scan", json={"bundle_id": "mock-low-confidence"}, headers=auth_header()
    )

    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == ScanOutcome.NEEDS_CONFIRMATION
    assert body["card"] is None
    assert len(body["choices"]) == 2
    # The price delta is the load-bearing number that justifies the confirm prompt.
    assert body["price_delta"] is not None


def test_scan_rejects_blank_bundle_id_with_error_envelope(client) -> None:  # noqa: ANN001
    response = client.post("/scan", json={"bundle_id": ""}, headers=auth_header())

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert "errors" in body["error"]["details"]


def test_request_id_is_echoed_back(client) -> None:  # noqa: ANN001
    response = client.get("/health", headers={"X-Request-ID": "trace-123"})
    assert response.headers["X-Request-ID"] == "trace-123"


# The test app is configured with a single allowed origin (conftest).
_ALLOWED_ORIGIN = "https://app.holofy.test"


def test_cors_allows_the_configured_origin_without_wildcarding(client) -> None:  # noqa: ANN001
    preflight = client.options(
        "/scan",
        headers={
            "Origin": _ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )

    assert preflight.status_code == 200
    # The origin is echoed back exactly — never reflected as "*", which is incompatible with
    # credentialed requests anyway.
    assert preflight.headers["access-control-allow-origin"] == _ALLOWED_ORIGIN
    assert preflight.headers["access-control-allow-credentials"] == "true"
    allowed_methods = preflight.headers["access-control-allow-methods"]
    assert "*" not in allowed_methods
    assert "POST" in allowed_methods


def test_cors_rejects_an_unconfigured_origin(client) -> None:  # noqa: ANN001
    preflight = client.options(
        "/scan",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "POST",
        },
    )

    # Deny-by-default: an unlisted origin gets no allow-origin grant.
    assert "access-control-allow-origin" not in preflight.headers


def test_cors_does_not_grant_an_unused_method(client) -> None:  # noqa: ANN001
    # PATCH isn't a verb the API serves, so it isn't in the allow-list (no wildcard). DELETE
    # *is* served now (account erasure), so it's a poor stand-in for "unused" — use PATCH.
    preflight = client.options(
        "/scan",
        headers={
            "Origin": _ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "PATCH",
        },
    )

    allowed = preflight.headers.get("access-control-allow-methods", "")
    assert "PATCH" not in allowed
