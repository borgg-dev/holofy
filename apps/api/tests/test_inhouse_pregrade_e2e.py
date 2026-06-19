"""Genuine grading end-to-end over HTTP: upload a real card image, then /pregrade with the
in-house grader. Both inputs are measured from pixels — centering (numpy) and corners/edges/
surface (the condition reader) — composed into an honest range. No mock grading, no network.
"""

from __future__ import annotations

from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app.config import CaptureStorageBackend, GradingBackend, PricingBackend, Settings
from app.db.base import Base
from app.main import create_app
from tests.conftest import auth_header

_DEV_SECRET = "test-secret"


def _bordered_card() -> bytes:
    # A centred, evenly-bordered card on a dark surface: centering can measure it and the
    # clean face reads high on corners/edges/surface.
    image = Image.new("RGB", (500, 700), (12, 12, 16))
    draw = ImageDraw.Draw(image)
    draw.rectangle((24, 24, 476, 676), fill=(235, 235, 235))
    draw.rectangle((64, 64, 436, 636), fill=(95, 95, 95))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def grading_client():
    settings = Settings(
        grading_provider=GradingBackend.INHOUSE,
        pricing_provider=PricingBackend.MOCK,
        capture_storage=CaptureStorageBackend.MEMORY,
        database_url="sqlite+aiosqlite://",
        auth_dev_secret=_DEV_SECRET,
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


def test_upload_then_inhouse_pregrade_estimates_from_real_pixels(grading_client) -> None:  # noqa: ANN001
    ref = grading_client.post(
        "/captures",
        files=[("files", ("card.png", _bordered_card(), "image/png"))],
        headers=auth_header(),
    ).json()["ref"]

    response = grading_client.post("/pregrade", json={"capture_ref": ref}, headers=auth_header())
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "estimated"
    # All four sub-scores present, including the in-house centering and the in-house condition.
    axes = {s["axis"] for s in body["sub_scores"]}
    assert axes == {"centering", "corners", "edges", "surface"}
    # Honest framing holds: a range and a P(≥), never a single grade.
    assert {"likely_low", "likely_high", "at_least", "p_at_least"} <= set(body["probability"])
    assert "grade" not in body["probability"]
