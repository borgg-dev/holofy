"""End-to-end coverage of the persisted, user-scoped, quota-guarded scan flow.

Exercises the slice's contract through the API: a scan records a ``ScanRecord`` with consent
off by default, opt-in consent is honored, the free tier's daily budget returns a 429 once
spent, and the quota is per-user (one collector's scans don't deplete another's). Runs on
mock providers against the in-memory database.
"""

from __future__ import annotations

from app.db.models import ScanOutcome, ScanRecord
from app.db.repositories import ScanRepository, UserRepository
from app.schemas.scan import ScanOutcome as ApiScanOutcome
from tests.conftest import auth_header


def _scans_for(client, subject: str) -> list[ScanRecord]:  # noqa: ANN001
    """Read a user's persisted scans straight from the DB, on the app's session loop."""
    app = client.app

    async def _read() -> list[ScanRecord]:
        async with app.state.session_factory() as session:
            users = UserRepository(session)
            user = await users.get_by_auth("dev_token", subject)
            assert user is not None
            return await ScanRepository(session).list_for_user(user.id)

    return client.portal.call(_read)


def test_scan_persists_a_record_with_consent_off_by_default(client) -> None:  # noqa: ANN001
    response = client.post(
        "/scan", json={"bundle_id": "mock-high-confidence"}, headers=auth_header()
    )
    assert response.status_code == 200

    records = _scans_for(client, "collector-1")
    assert len(records) == 1
    record = records[0]
    assert record.outcome == ScanOutcome.RESOLVED
    assert record.capture_ref == "mock-high-confidence"
    assert record.resolved_card_id is not None
    # Privacy-by-design: a scan is never training-eligible unless explicitly opted in.
    assert record.training_consent is False
    assert record.consent_revoked_at is None


def test_scan_records_explicit_training_consent_when_opted_in(client) -> None:  # noqa: ANN001
    response = client.post(
        "/scan",
        json={
            "bundle_id": "mock-high-confidence",
            "training_consent": True,
            "consent_note": "onboarding v1",
        },
        headers=auth_header("collector-consent"),
    )
    assert response.status_code == 200

    records = _scans_for(client, "collector-consent")
    assert len(records) == 1
    assert records[0].training_consent is True
    assert records[0].consent_note == "onboarding v1"


def test_low_confidence_scan_persists_without_a_resolved_card(client) -> None:  # noqa: ANN001
    response = client.post(
        "/scan", json={"bundle_id": "mock-low-confidence"}, headers=auth_header()
    )
    assert response.json()["outcome"] == ApiScanOutcome.NEEDS_CONFIRMATION

    records = _scans_for(client, "collector-1")
    assert records[0].outcome == ScanOutcome.NEEDS_CONFIRMATION
    assert records[0].resolved_card_id is None
    # The ranked hypotheses are kept as the variant-disambiguation training signal.
    assert len(records[0].candidates) == 2


def test_free_tier_quota_returns_429_past_the_daily_limit(client) -> None:  # noqa: ANN001
    headers = auth_header("heavy-scanner")
    # The free tier is 8 scans/day; the ninth is refused.
    for _ in range(8):
        ok = client.post(
            "/scan", json={"bundle_id": "mock-high-confidence"}, headers=headers
        )
        assert ok.status_code == 200

    refused = client.post(
        "/scan", json={"bundle_id": "mock-high-confidence"}, headers=headers
    )
    assert refused.status_code == 429
    body = refused.json()["error"]
    assert body["code"] == "quota_exceeded"
    assert body["details"]["limit"] == 8
    assert body["details"]["reset_seconds"] > 0

    # A refused scan costs no recognition credit and logs no record: only 8 persisted.
    assert len(_scans_for(client, "heavy-scanner")) == 8


def test_quota_is_scoped_per_user(client) -> None:  # noqa: ANN001
    spent = auth_header("user-a")
    for _ in range(8):
        client.post(
            "/scan", json={"bundle_id": "mock-high-confidence"}, headers=spent
        )
    assert (
        client.post(
            "/scan", json={"bundle_id": "mock-high-confidence"}, headers=spent
        ).status_code
        == 429
    )

    # A different user starts with a full budget.
    fresh = auth_header("user-b")
    assert (
        client.post(
            "/scan", json={"bundle_id": "mock-high-confidence"}, headers=fresh
        ).status_code
        == 200
    )
