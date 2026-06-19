"""API coverage for the training-consent endpoints — read, grant, revoke.

Training consent is off by default and separate from app-usage (charter §3.5): a fresh
account reads ``granted=false`` with nothing consented, an explicit grant opts existing
captures in, and a revoke withdraws them (marking them for lake purge). These run through the
TestClient against an in-memory database with the mock data-lake sink, so the same path the
mobile privacy screen drives is exercised end to end.
"""

from __future__ import annotations

from app.datalake.mock import MockDataLakeSink
from app.schemas.datalake import TrainingExampleKind
from tests.conftest import auth_header


def _sink(client) -> MockDataLakeSink:  # noqa: ANN001
    sink = client.app.state.datalake_sink
    assert isinstance(sink, MockDataLakeSink)
    return sink


def test_consent_requires_authentication(client) -> None:  # noqa: ANN001
    assert client.get("/consent/training").status_code == 401
    assert client.put("/consent/training", json={"granted": True}).status_code == 401


def test_fresh_account_reads_consent_off_by_default(client) -> None:  # noqa: ANN001
    response = client.get("/consent/training", headers=auth_header())

    assert response.status_code == 200
    body = response.json()
    assert body["granted"] is False
    assert body["consented"] == {"scans": 0, "pregrades": 0, "authenticity": 0}


def test_grant_persists_with_zero_captures(client) -> None:  # noqa: ANN001
    # The account-level fix: opting in *before* having any captures must stick. The state is
    # read off the account, not derived from per-record counts (which would read back false).
    granted = client.put(
        "/consent/training", json={"granted": True}, headers=auth_header()
    )
    assert granted.status_code == 200
    assert granted.json()["granted"] is True
    assert granted.json()["consented"] == {"scans": 0, "pregrades": 0, "authenticity": 0}

    # A fresh read reflects the account state with still nothing captured.
    reread = client.get("/consent/training", headers=auth_header())
    assert reread.json()["granted"] is True
    assert reread.json()["consented"]["scans"] == 0


def test_opted_in_account_stamps_new_captures_consented(client) -> None:  # noqa: ANN001
    # Opt the account in first, with no at-capture flag on the scan: the new capture inherits
    # the standing account consent and reaches the lake.
    sink = _sink(client)
    client.put("/consent/training", json={"granted": True}, headers=auth_header())

    client.post(
        "/scan", json={"bundle_id": "mock-high-confidence"}, headers=auth_header()
    )
    assert len(sink.examples_of(TrainingExampleKind.SCAN)) == 1
    assert client.get("/consent/training", headers=auth_header()).json()["consented"]["scans"] == 1


def test_revoked_account_stamps_new_captures_off_and_emits_nothing(client) -> None:  # noqa: ANN001
    # Opt in, then revoke at the account level. A subsequent scan — with no at-capture flag —
    # inherits the revoked account state, so it is stamped not-consented and emits nothing.
    sink = _sink(client)
    client.put("/consent/training", json={"granted": True}, headers=auth_header())
    client.put("/consent/training", json={"granted": False}, headers=auth_header())

    client.post(
        "/scan", json={"bundle_id": "mock-high-confidence"}, headers=auth_header()
    )
    assert sink.examples == []
    assert client.get("/consent/training", headers=auth_header()).json()["granted"] is False


def test_grant_then_revoke_flips_consent_state_for_existing_captures(client) -> None:  # noqa: ANN001
    # A consent-off scan exists as history but isn't training-eligible yet.
    client.post(
        "/scan", json={"bundle_id": "mock-high-confidence"}, headers=auth_header()
    )
    assert client.get("/consent/training", headers=auth_header()).json()["granted"] is False

    granted = client.put(
        "/consent/training", json={"granted": True, "note": "privacy screen v1"},
        headers=auth_header(),
    )
    assert granted.status_code == 200
    body = granted.json()
    assert body["granted"] is True
    assert body["consented"]["scans"] == 1

    revoked = client.put(
        "/consent/training", json={"granted": False}, headers=auth_header()
    )
    assert revoked.status_code == 200
    assert revoked.json()["granted"] is False
    assert revoked.json()["consented"]["scans"] == 0


def test_consented_scan_reaches_the_lake_and_revoke_purges_it(client) -> None:  # noqa: ANN001
    sink = _sink(client)

    # A scan with consent opted in at capture emits one example.
    client.post(
        "/scan",
        json={"bundle_id": "mock-high-confidence", "training_consent": True},
        headers=auth_header(),
    )
    assert len(sink.examples_of(TrainingExampleKind.SCAN)) == 1

    # Revoking consent (GDPR Art. 7(3)) PURGES the already-emitted example, not just stops
    # future ones — withdrawing consent must remove the data already in the lake.
    client.put("/consent/training", json={"granted": False}, headers=auth_header())
    assert len(sink.examples_of(TrainingExampleKind.SCAN)) == 0

    # And a subsequent default scan (consent off) adds nothing more.
    client.post(
        "/scan", json={"bundle_id": "mock-high-confidence"}, headers=auth_header()
    )
    assert len(sink.examples_of(TrainingExampleKind.SCAN)) == 0


def test_non_consented_scan_never_reaches_the_lake(client) -> None:  # noqa: ANN001
    # The privacy hard line at the API boundary: a default scan emits zero examples.
    sink = _sink(client)
    client.post(
        "/scan", json={"bundle_id": "mock-high-confidence"}, headers=auth_header()
    )
    assert sink.examples == []
