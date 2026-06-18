"""API-level coverage for /pregrade via the TestClient — auth, the estimated and retake
outcomes, persistence, and the unresolvable-capture error. Runs on mock providers and the
synthetic capture store against an in-memory database.
"""

from __future__ import annotations

from app.api.dependencies import get_grading_provider
from app.db.models import PreGradeRecord
from app.db.repositories import PreGradeRepository, UserRepository
from app.providers.base import GradingCapture
from app.schemas.grading import GradingAxis, PregradeStatus, SubScore
from tests.conftest import auth_header


def _pregrades_for(client, subject: str) -> list[PreGradeRecord]:  # noqa: ANN001
    """Read a user's persisted pre-grades straight from the DB, on the app's session loop."""
    app = client.app

    async def _read() -> list[PreGradeRecord]:
        async with app.state.session_factory() as session:
            user = await UserRepository(session).get_by_auth("dev_token", subject)
            assert user is not None
            return await PreGradeRepository(session).list_for_user(user.id)

    return client.portal.call(_read)


def test_pregrade_requires_authentication(client) -> None:  # noqa: ANN001
    response = client.post("/pregrade", json={"capture_ref": "capture-centered"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


def test_pregrade_estimates_a_probability_range_with_disclaimer(client) -> None:  # noqa: ANN001
    response = client.post(
        "/pregrade", json={"capture_ref": "capture-centered"}, headers=auth_header()
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == PregradeStatus.ESTIMATED
    # Honest framing: a range and a disclaimer, never a single grade.
    assert body["probability"] is not None
    assert "grade" not in body["probability"]
    assert {"likely_low", "likely_high", "at_least", "p_at_least"} <= set(body["probability"])
    assert body["reasons"] is None
    assert "pre-screen" in body["disclaimer"].lower()
    # The four sub-scores, including in-house centering.
    axes = {s["axis"] for s in body["sub_scores"]}
    assert axes == {"centering", "corners", "edges", "surface"}


def test_pregrade_refuses_full_bleed_capture_with_a_retake_not_a_500(client) -> None:  # noqa: ANN001
    response = client.post(
        "/pregrade", json={"capture_ref": "capture-full-bleed"}, headers=auth_header()
    )

    # Refuse-on-bad-capture is a clean typed 200, not an error.
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == PregradeStatus.RETAKE
    assert body["probability"] is None
    assert body["reasons"]


def test_pregrade_unknown_capture_reference_is_a_typed_404(client) -> None:  # noqa: ANN001
    response = client.post(
        "/pregrade", json={"capture_ref": "not-a-capture"}, headers=auth_header()
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "capture_not_found"


def test_pregrade_rejects_blank_capture_ref_with_error_envelope(client) -> None:  # noqa: ANN001
    response = client.post("/pregrade", json={"capture_ref": ""}, headers=auth_header())

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


class _ImageCountSpyGrader:
    """A grader that records the ``image_count`` the endpoint threaded onto the capture."""

    def __init__(self) -> None:
        self.seen_image_count: int | None = None

    async def grade(self, capture: GradingCapture) -> list[SubScore]:
        self.seen_image_count = capture.image_count
        return [
            SubScore(axis=GradingAxis.CORNERS, score=9.0, confidence=0.9),
            SubScore(axis=GradingAxis.EDGES, score=9.0, confidence=0.9),
            SubScore(axis=GradingAxis.SURFACE, score=9.0, confidence=0.9),
        ]


def test_pregrade_threads_the_request_image_count_to_the_grader(client) -> None:  # noqa: ANN001
    # The multi-angle count from the capture bundle must reach the provider — a single-frame
    # capture caps what surface/holo can claim, so it can't be hardcoded to one.
    spy = _ImageCountSpyGrader()
    client.app.dependency_overrides[get_grading_provider] = lambda: spy
    try:
        response = client.post(
            "/pregrade",
            json={"capture_ref": "capture-centered", "image_count": 4},
            headers=auth_header(),
        )
    finally:
        client.app.dependency_overrides.pop(get_grading_provider, None)

    assert response.status_code == 200
    assert spy.seen_image_count == 4


def test_pregrade_image_count_defaults_to_one_when_omitted(client) -> None:  # noqa: ANN001
    spy = _ImageCountSpyGrader()
    client.app.dependency_overrides[get_grading_provider] = lambda: spy
    try:
        client.post(
            "/pregrade", json={"capture_ref": "capture-centered"}, headers=auth_header()
        )
    finally:
        client.app.dependency_overrides.pop(get_grading_provider, None)

    assert spy.seen_image_count == 1


def test_pregrade_persists_the_result_against_the_user(client) -> None:  # noqa: ANN001
    client.post("/pregrade", json={"capture_ref": "capture-centered"}, headers=auth_header())
    client.post("/pregrade", json={"capture_ref": "capture-full-bleed"}, headers=auth_header())

    records = _pregrades_for(client, "collector-1")
    assert len(records) == 2
    statuses = {r.status for r in records}
    # StrEnum compares equal to its stored string value across the SQLite round-trip.
    assert PregradeStatus.ESTIMATED in statuses
    assert PregradeStatus.RETAKE in statuses
    # The estimated record carries a range; the retake one does not — honest framing at the row.
    estimated = next(r for r in records if r.status == PregradeStatus.ESTIMATED)
    assert estimated.likely_low is not None and estimated.p_at_least is not None
    retake = next(r for r in records if r.status == PregradeStatus.RETAKE)
    assert retake.likely_low is None and retake.retake_reasons
