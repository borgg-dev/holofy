"""API-level coverage via FastAPI's TestClient — health, the two scan outcomes, the
error envelope, and the request-id round-trip. Runs entirely on mock providers.
"""

from __future__ import annotations

from app.schemas.scan import ScanOutcome


def test_health_reports_active_backends_and_region(client) -> None:  # noqa: ANN001
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["recognition_provider"] == "mock"
    assert body["pricing_provider"] == "mock"
    assert body["data_region"].startswith("eu-")


def test_scan_resolves_high_confidence_bundle(client) -> None:  # noqa: ANN001
    response = client.post("/scan", json={"bundle_id": "mock-high-confidence"})

    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == ScanOutcome.RESOLVED
    assert body["card"]["identity"]["canonical_id"] == "base1-2"
    assert body["card"]["price"]["currency"] == "EUR"
    assert body["choices"] is None


def test_scan_low_confidence_bundle_requests_confirmation(client) -> None:  # noqa: ANN001
    response = client.post("/scan", json={"bundle_id": "mock-low-confidence"})

    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == ScanOutcome.NEEDS_CONFIRMATION
    assert body["card"] is None
    assert len(body["choices"]) == 2
    # The price delta is the load-bearing number that justifies the confirm prompt.
    assert body["price_delta"] is not None


def test_scan_rejects_blank_bundle_id_with_error_envelope(client) -> None:  # noqa: ANN001
    response = client.post("/scan", json={"bundle_id": ""})

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert "errors" in body["error"]["details"]


def test_request_id_is_echoed_back(client) -> None:  # noqa: ANN001
    response = client.get("/health", headers={"X-Request-ID": "trace-123"})
    assert response.headers["X-Request-ID"] == "trace-123"
