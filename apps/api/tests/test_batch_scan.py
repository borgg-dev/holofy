"""End-to-end coverage of the stack/batch scan slice (P4.1).

Exercises the contract through the API on mock providers: a mixed stack returns the right
per-item outcomes; recognition — the COGS unit — is charged per capture *before* it runs, so a
spent budget drives zero recognizer calls (the headline cost guarantee); repeats of one card
collapse into a single banked result with the merged ``count`` (without refunding the units the
flips cost); auth is required; and a deduped stack persists one ``ScanRecord`` per card — never
one per flip — with consent off by default and a single consented example reaching the lake when
opted in.
"""

from __future__ import annotations

from app.db.models import ScanRecord
from app.db.repositories import ScanRepository, UserRepository
from app.providers.base import CaptureBundle
from app.providers.recognition.mock import MockRecognitionProvider
from app.schemas.batch_scan import MAX_BATCH_ITEMS
from app.schemas.cards import RecognitionResult
from app.schemas.datalake import TrainingExampleKind
from tests.conftest import auth_header


class _CountingRecognizer:
    """Wraps the mock recognizer and tallies every call — a spy for the COGS guarantee.

    Each ``recognize`` is one Ximilar credit in production, so the call count *is* the COGS the
    quota exists to bound. The tests assert it directly: a capture skipped for quota must never
    reach here.
    """

    def __init__(self) -> None:
        self._inner = MockRecognitionProvider()
        self.calls = 0

    async def recognize(self, bundle: CaptureBundle) -> RecognitionResult:
        self.calls += 1
        return await self._inner.recognize(bundle)


def _install_spy(client) -> _CountingRecognizer:  # noqa: ANN001
    spy = _CountingRecognizer()
    client.app.state.recognition_provider = spy
    return spy


def _drain_budget(client, subject: str) -> None:  # noqa: ANN001
    """Spend the full daily scan budget on single calls, leaving zero remaining."""
    headers = auth_header(subject)
    while (
        client.post(
            "/scan", json={"bundle_id": "mock-high-confidence"}, headers=headers
        ).status_code
        == 200
    ):
        pass


def _scans_for(client, subject: str) -> list[ScanRecord]:  # noqa: ANN001
    app = client.app

    async def _read() -> list[ScanRecord]:
        async with app.state.session_factory() as session:
            user = await UserRepository(session).get_by_auth("dev_token", subject)
            assert user is not None
            return await ScanRepository(session).list_for_user(user.id)

    return client.portal.call(_read)


def _by_outcome(items: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for item in items:
        grouped.setdefault(item["outcome"], []).append(item)
    return grouped


def test_mixed_batch_returns_per_item_outcomes(client) -> None:  # noqa: ANN001
    response = client.post(
        "/scan/batch",
        json={
            "items": [
                {"bundle_id": "mock-high-confidence"},
                {"bundle_id": "mock-low-confidence"},
                {"bundle_id": "mock-unrecognized"},
            ]
        },
        headers=auth_header("stacker"),
    )
    assert response.status_code == 200
    body = response.json()
    grouped = _by_outcome(body["items"])

    assert len(grouped["resolved"]) == 1
    assert grouped["resolved"][0]["card"]["identity"]["name"] == "Tidecaller Leviath"
    assert len(grouped["needs_confirmation"]) == 1
    assert len(grouped["needs_confirmation"][0]["choices"]) == 2
    assert grouped["needs_confirmation"][0]["price_delta"] == "732.60"
    assert len(grouped["unrecognized"]) == 1

    # Every capture was recognized, so every capture cost one credit — the honest COGS, including
    # the unrecognized read (the recognizer still ran on it).
    assert body["quota"]["charged"] == 3
    assert body["quota"]["rejected"] == 0
    assert body["quota"]["remaining"] == 5  # 8/day - 3


def test_exhausted_budget_drives_zero_recognitions(client) -> None:  # noqa: ANN001
    # The exact falsification the auditor used: a fully spent budget plus a maximal batch must
    # not spend a single recognition credit.
    _drain_budget(client, "spent")
    spy = _install_spy(client)

    items = [{"bundle_id": "mock-high-confidence"} for _ in range(MAX_BATCH_ITEMS)]
    response = client.post(
        "/scan/batch", json={"items": items}, headers=auth_header("spent")
    )
    body = response.json()

    # The COGS guarantee: with no budget left, the recognizer is never called.
    assert spy.calls == 0
    assert body["quota"]["charged"] == 0
    assert body["quota"]["rejected"] == MAX_BATCH_ITEMS

    quota_exceeded = _by_outcome(body["items"])["quota_exceeded"]
    assert len(quota_exceeded) == 1  # one item carrying every capture that hit the wall
    assert quota_exceeded[0]["count"] == MAX_BATCH_ITEMS
    assert len(_scans_for(client, "spent")) == 8  # the singles only; nothing from the batch


def test_partial_budget_bounds_recognitions_to_remaining(client) -> None:  # noqa: ANN001
    # Spend 5 of 8, leaving exactly 3 — then submit 5 distinct captures.
    headers = auth_header("partial")
    for _ in range(5):
        assert (
            client.post(
                "/scan", json={"bundle_id": "mock-high-confidence"}, headers=headers
            ).status_code
            == 200
        )
    spy = _install_spy(client)

    response = client.post(
        "/scan/batch",
        json={
            "items": [
                {"bundle_id": "mock-high-confidence"},
                {"bundle_id": "mock-high-confidence-2"},
                {"bundle_id": "mock-low-confidence"},
                {"bundle_id": "mock-unrecognized"},
                {"bundle_id": "mock-high-confidence"},
            ]
        },
        headers=headers,
    )
    body = response.json()

    # Recognition is bounded by the remaining budget: exactly 3 calls, two captures rejected
    # before they ever reach the recognizer.
    assert spy.calls == 3
    assert body["quota"]["charged"] == 3
    assert body["quota"]["rejected"] == 2
    assert body["quota"]["remaining"] == 0
    assert _by_outcome(body["items"])["quota_exceeded"][0]["count"] == 2


def test_dedupe_collapses_repeats_but_still_charges_each_capture(client) -> None:  # noqa: ANN001
    # The same card flipped past three times, plus a different card once.
    response = client.post(
        "/scan/batch",
        json={
            "items": [
                {"bundle_id": "mock-high-confidence"},
                {"bundle_id": "mock-high-confidence"},
                {"bundle_id": "mock-high-confidence"},
                {"bundle_id": "mock-high-confidence-2"},
            ]
        },
        headers=auth_header("flipper"),
    )
    body = response.json()
    resolved = _by_outcome(body["items"])["resolved"]

    assert len(resolved) == 2  # two distinct cards, not four items
    tide = next(r for r in resolved if r["card"]["identity"]["name"] == "Tidecaller Leviath")
    assert tide["count"] == 3
    assert tide["capture_refs"] == ["mock-high-confidence"] * 3

    # Dedupe banks each card once (two records), but every capture still spent a credit — a
    # re-flip is a real recognition call, so it is honestly charged, never refunded.
    assert body["quota"]["charged"] == 4
    assert len(_scans_for(client, "flipper")) == 2


def test_low_confidence_repeats_dedupe_on_top_candidate(client) -> None:  # noqa: ANN001
    response = client.post(
        "/scan/batch",
        json={
            "items": [
                {"bundle_id": "mock-low-confidence"},
                {"bundle_id": "mock-low-confidence"},
            ]
        },
        headers=auth_header("low-flipper"),
    )
    body = response.json()
    confirm = _by_outcome(body["items"])["needs_confirmation"]
    assert len(confirm) == 1
    assert confirm[0]["count"] == 2
    assert body["quota"]["charged"] == 2  # two captures recognized, banked as one card


def test_threshold_straddle_collapses_across_outcomes(client) -> None:  # noqa: ANN001
    # One physical card read confident on one flip and below the confirm threshold on the next —
    # frame-to-frame jitter around 0.85. Both reads share the top canonical id (origins-12), so
    # they must collapse to one banked card despite the differing outcomes.
    from app.providers.recognition.mock import (
        _EMBERWYRM_ECHO,
        _EMBERWYRM_ORIGINS,
    )
    from app.schemas.cards import RecognitionCandidate

    straddle = {
        # Above the 0.85 confirm threshold → resolved on this flip.
        "mock-emberwyrm-confident": [
            RecognitionCandidate(identity=_EMBERWYRM_ORIGINS, confidence=0.9),
        ],
        # Below it → needs_confirmation on this flip, same top candidate.
        "mock-emberwyrm-unsure": [
            RecognitionCandidate(identity=_EMBERWYRM_ORIGINS, confidence=0.8),
            RecognitionCandidate(identity=_EMBERWYRM_ECHO, confidence=0.7),
        ],
    }

    class _StraddleRecognizer:
        async def recognize(self, bundle: CaptureBundle) -> RecognitionResult:
            return RecognitionResult(candidates=straddle[bundle.bundle_id])

    client.app.state.recognition_provider = _StraddleRecognizer()

    response = client.post(
        "/scan/batch",
        json={
            "items": [
                {"bundle_id": "mock-emberwyrm-confident"},
                {"bundle_id": "mock-emberwyrm-unsure"},
            ]
        },
        headers=auth_header("straddler"),
    )
    body = response.json()

    # One physical card, one banked item with count 2 — not split across resolved/confirm.
    assert len(body["items"]) == 1
    assert body["items"][0]["count"] == 2
    # The confident read wins the merged outcome, so the user sees the priced result.
    assert body["items"][0]["outcome"] == "resolved"
    assert body["quota"]["charged"] == 2
    assert len(_scans_for(client, "straddler")) == 1


def test_batch_requires_auth(client) -> None:  # noqa: ANN001
    response = client.post(
        "/scan/batch", json={"items": [{"bundle_id": "mock-high-confidence"}]}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


def test_empty_batch_is_rejected(client) -> None:  # noqa: ANN001
    response = client.post(
        "/scan/batch", json={"items": []}, headers=auth_header("empty")
    )
    assert response.status_code == 422


def test_oversized_batch_is_rejected(client) -> None:  # noqa: ANN001
    items = [{"bundle_id": "mock-high-confidence"}] * (MAX_BATCH_ITEMS + 1)
    response = client.post(
        "/scan/batch", json={"items": items}, headers=auth_header("oversized")
    )
    assert response.status_code == 422


def test_consent_off_by_default_nothing_reaches_the_lake(client) -> None:  # noqa: ANN001
    client.post(
        "/scan/batch",
        json={"items": [{"bundle_id": "mock-high-confidence"}]},
        headers=auth_header("no-consent"),
    )
    records = _scans_for(client, "no-consent")
    assert len(records) == 1
    assert records[0].training_consent is False

    # The no-consent batch wrote history but emitted no training example to the lake.
    sink = client.app.state.datalake_sink
    assert sink.examples_of(TrainingExampleKind.SCAN) == []


def test_consented_batch_emits_one_example_per_deduped_card(client) -> None:  # noqa: ANN001
    # Opt the account in first, then run a stack with one card flipped twice.
    headers = auth_header("consented")
    assert (
        client.put("/consent/training", json={"granted": True}, headers=headers).status_code
        == 200
    )
    client.post(
        "/scan/batch",
        json={
            "items": [
                {"bundle_id": "mock-high-confidence"},
                {"bundle_id": "mock-high-confidence"},
            ]
        },
        headers=headers,
    )

    records = _scans_for(client, "consented")
    assert len(records) == 1  # deduped: one record for the twice-flipped card
    assert records[0].training_consent is True

    sink = client.app.state.datalake_sink
    emitted = [
        e
        for e in sink.examples_of(TrainingExampleKind.SCAN)
        if e.user_id == records[0].user_id
    ]
    assert len(emitted) == 1  # one consented example, not one per flip
