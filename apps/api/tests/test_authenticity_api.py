"""API-level coverage for /authenticity via the TestClient — auth, the assessed / retake /
not-assessed outcomes, persistence, the value gate, and the unresolvable-capture and
unknown-card errors. Runs on mock providers and the synthetic capture store against an
in-memory database.

The cards the screen runs against are landed directly in the catalog on the app's session
loop (the screen needs a resolved card; scanning to land one is covered elsewhere). A
high-value card (``origins-12``, ~€757 via the mock pricer) clears the value threshold; a
cheap one (``echo-12``, ~€24) falls below it.
"""

from __future__ import annotations

from app.api.dependencies import get_authenticity_provider
from app.db.models import AuthenticityRecord
from app.db.models.enums import Variant
from app.db.repositories import AuthenticityRepository, CardRepository, UserRepository
from app.providers.base import AuthenticityCapture
from app.providers.authenticity.mock import MockAuthenticityProvider
from app.schemas.authenticity import AuthenticitySignal, AuthenticityStatus, RiskBand
from tests.conftest import auth_header


def _land_card(client, *, canonical_id: str, variant: Variant = Variant.HOLO) -> None:  # noqa: ANN001
    """Insert a catalog card on the app's session loop so the endpoint can resolve it.

    ``set_code`` / ``collector_number`` mirror the recognition mock's invented cards so the
    catalog cross-check resolves them against the reference checker.
    """
    app = client.app
    set_code = canonical_id.rsplit("-", 1)[0]
    numbers = {"origins-12": "12/120", "echo-12": "12/95", "origins-99": "99/120"}

    async def _insert() -> None:
        async with app.state.session_factory() as session:
            await CardRepository(session).upsert(
                canonical_id=canonical_id,
                name="Emberwyrm Sovereign",
                set_name="Origins Vault",
                set_code=set_code,
                collector_number=numbers[canonical_id],
                language="en",
                variant=variant,
            )
            await session.commit()

    client.portal.call(_insert)


def _screens_for(client, subject: str) -> list[AuthenticityRecord]:  # noqa: ANN001
    app = client.app

    async def _read() -> list[AuthenticityRecord]:
        async with app.state.session_factory() as session:
            user = await UserRepository(session).get_by_auth("dev_token", subject)
            assert user is not None
            return await AuthenticityRepository(session).list_for_user(user.id)

    return client.portal.call(_read)


def test_authenticity_requires_authentication(client) -> None:  # noqa: ANN001
    response = client.post(
        "/authenticity", json={"capture_ref": "capture-authentic", "card_id": "origins-12"}
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


def test_authenticity_assesses_a_risk_band_with_disclaimer(client) -> None:  # noqa: ANN001
    _land_card(client, canonical_id="origins-12")

    response = client.post(
        "/authenticity",
        json={"capture_ref": "capture-authentic", "card_id": "origins-12"},
        headers=auth_header(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == AuthenticityStatus.ASSESSED
    # Honest framing: a band and a disclaimer, never a fake/genuine verdict.
    assert body["assessment"]["risk_band"] in {b.value for b in RiskBand}
    assert "verdict" not in body["assessment"]
    assert "not a verdict" in body["disclaimer"].lower()
    # The catalog cross-check rides alongside the four visual signals.
    kinds = {s["kind"] for s in body["assessment"]["signals"]}
    assert "catalog_existence" in kinds
    assert body["assessment"]["recommend_authentication"] is True


def test_authenticity_never_emits_a_verdict_field_or_value(client) -> None:  # noqa: ANN001
    # The §3.5 hard gate at the wire level: no response field is verdict-shaped, and the band
    # value is the three-band scale — not a fake/genuine boolean. (Checked structurally; the
    # honest disclaimer is allowed to say "not a determination that a card is genuine".)
    _land_card(client, canonical_id="origins-12")
    response = client.post(
        "/authenticity",
        json={"capture_ref": "capture-mixed", "card_id": "origins-12"},
        headers=auth_header(),
    )
    body = response.json()
    forbidden_fields = {"is_fake", "is_genuine", "fake", "genuine", "verdict", "authentic"}
    assert forbidden_fields.isdisjoint(body)
    assert forbidden_fields.isdisjoint(body["assessment"])
    assert body["assessment"]["risk_band"] in {"strong_signals", "inconclusive", "elevated_risk"}


def test_authenticity_refuses_a_poor_capture_with_a_retake_not_a_500(client) -> None:  # noqa: ANN001
    _land_card(client, canonical_id="origins-12")
    response = client.post(
        "/authenticity",
        json={"capture_ref": "capture-poor", "card_id": "origins-12"},
        headers=auth_header(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == AuthenticityStatus.RETAKE
    assert body["assessment"] is None
    assert body["reasons"]


def test_authenticity_below_value_threshold_is_not_assessed(client) -> None:  # noqa: ANN001
    # echo-12 prices at ~€24 — below the €50 screening threshold; cheap cards aren't faked.
    _land_card(client, canonical_id="echo-12")
    response = client.post(
        "/authenticity",
        json={"capture_ref": "capture-authentic", "card_id": "echo-12"},
        headers=auth_header(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == AuthenticityStatus.NOT_ASSESSED
    assert body["assessment"] is None
    assert body["reasons"]


def test_authenticity_unknown_card_is_a_typed_404(client) -> None:  # noqa: ANN001
    response = client.post(
        "/authenticity",
        json={"capture_ref": "capture-authentic", "card_id": "not-a-card"},
        headers=auth_header(),
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "card_not_found"


def test_authenticity_unknown_capture_reference_is_a_typed_404(client) -> None:  # noqa: ANN001
    _land_card(client, canonical_id="origins-12")
    response = client.post(
        "/authenticity",
        json={"capture_ref": "not-a-capture", "card_id": "origins-12"},
        headers=auth_header(),
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "capture_not_found"


def test_authenticity_rejects_blank_capture_ref_with_error_envelope(client) -> None:  # noqa: ANN001
    response = client.post(
        "/authenticity", json={"capture_ref": "", "card_id": "origins-12"}, headers=auth_header()
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_authenticity_free_tier_quota_returns_429_past_the_daily_limit(client) -> None:  # noqa: ANN001
    # /authenticity draws on the same free-tier budget as /scan and /pregrade — the ninth
    # screen of the day is refused, mirroring the scan-flow quota gate, and a refused screen
    # costs no screening credit and logs no record.
    _land_card(client, canonical_id="origins-12")
    headers = auth_header("heavy-authenticator")
    for _ in range(8):
        ok = client.post(
            "/authenticity",
            json={"capture_ref": "capture-authentic", "card_id": "origins-12"},
            headers=headers,
        )
        assert ok.status_code == 200

    refused = client.post(
        "/authenticity",
        json={"capture_ref": "capture-authentic", "card_id": "origins-12"},
        headers=headers,
    )
    assert refused.status_code == 429
    body = refused.json()["error"]
    assert body["code"] == "quota_exceeded"
    assert body["details"]["limit"] == 8
    assert body["details"]["reset_seconds"] > 0

    # The refused screen left no record: only the 8 allowed screens persisted.
    assert len(_screens_for(client, "heavy-authenticator")) == 8


def test_authenticity_quota_is_shared_with_scans(client) -> None:  # noqa: ANN001
    # The shared "scan:{user_id}" key can't be sidestepped by hopping endpoints: spending the
    # budget on /scan leaves /authenticity refused for the same user.
    _land_card(client, canonical_id="origins-12")
    headers = auth_header("budget-hopper")
    for _ in range(8):
        client.post("/scan", json={"bundle_id": "mock-high-confidence"}, headers=headers)

    refused = client.post(
        "/authenticity",
        json={"capture_ref": "capture-authentic", "card_id": "origins-12"},
        headers=headers,
    )
    assert refused.status_code == 429
    assert refused.json()["error"]["code"] == "quota_exceeded"


class _ImageCountSpyProvider:
    """Wraps the mock provider, recording the ``image_count`` the endpoint threaded through."""

    def __init__(self) -> None:
        self._inner = MockAuthenticityProvider()
        self.seen_image_count: int | None = None

    async def analyze(self, capture: AuthenticityCapture) -> list[AuthenticitySignal]:
        self.seen_image_count = capture.image_count
        return await self._inner.analyze(capture)


def test_authenticity_threads_the_request_image_count_to_the_provider(client) -> None:  # noqa: ANN001
    # The holo signature needs multiple tilt angles; the multi-angle count must reach the
    # provider rather than being hardcoded to one.
    _land_card(client, canonical_id="origins-12")
    spy = _ImageCountSpyProvider()
    client.app.dependency_overrides[get_authenticity_provider] = lambda: spy
    try:
        response = client.post(
            "/authenticity",
            json={
                "capture_ref": "capture-authentic",
                "card_id": "origins-12",
                "image_count": 3,
            },
            headers=auth_header(),
        )
    finally:
        client.app.dependency_overrides.pop(get_authenticity_provider, None)

    assert response.status_code == 200
    assert spy.seen_image_count == 3


def test_authenticity_persists_the_result_against_the_user(client) -> None:  # noqa: ANN001
    _land_card(client, canonical_id="origins-12")
    _land_card(client, canonical_id="echo-12")
    client.post(
        "/authenticity",
        json={"capture_ref": "capture-authentic", "card_id": "origins-12"},
        headers=auth_header(),
    )
    client.post(
        "/authenticity",
        json={"capture_ref": "capture-authentic", "card_id": "echo-12"},
        headers=auth_header(),
    )

    records = _screens_for(client, "collector-1")
    assert len(records) == 2
    statuses = {r.status for r in records}
    assert AuthenticityStatus.ASSESSED in statuses
    assert AuthenticityStatus.NOT_ASSESSED in statuses
    # The assessed record carries a band; the not-assessed one carries reasons and no band —
    # honest framing at the row, and never a boolean verdict column.
    assessed = next(r for r in records if r.status == AuthenticityStatus.ASSESSED)
    assert assessed.risk_band is not None and assessed.signals
    skipped = next(r for r in records if r.status == AuthenticityStatus.NOT_ASSESSED)
    assert skipped.risk_band is None and skipped.reasons
