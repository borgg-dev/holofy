"""Genuine end-to-end over HTTP: upload a real card image, then scan it with the in-house
recognizer (detect → OCR → resolve) and get back the right identified, priced card — no
fixtures, no mock recognition, no network. This is the proof the owned pipeline works as a
whole, exercised through the same FastAPI surface the mobile app calls.

Uses the real RapidOCR engine, so it's marked `ocr` and skips cleanly if it isn't installed.
"""

from __future__ import annotations

from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont

from app.config import (
    CaptureStorageBackend,
    CatalogBackend,
    PricingBackend,
    RecognitionBackend,
    Settings,
)
from app.db.base import Base
from app.main import create_app
from tests.conftest import auth_header

_DEV_SECRET = "test-secret"

pytestmark = pytest.mark.ocr


def _rendered_card(name: str, number: str) -> bytes:
    width, height = 420, 580
    image = Image.new("RGB", (width, height), (15, 15, 20))
    draw = ImageDraw.Draw(image)
    draw.rectangle((30, 30, width - 30, height - 30), fill=(238, 238, 238))
    draw.text((55, 55), name, fill=(10, 10, 10), font=ImageFont.truetype("DejaVuSans-Bold.ttf", 34))
    draw.text(
        (55, height - 90), number, fill=(10, 10, 10), font=ImageFont.truetype("DejaVuSans-Bold.ttf", 26)
    )
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def inhouse_client():
    pytest.importorskip("rapidocr_onnxruntime")
    settings = Settings(
        recognition_provider=RecognitionBackend.INHOUSE,
        # Resolve the rendered seed cards offline (the production default is live TCGdex).
        catalog_provider=CatalogBackend.INMEMORY,
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


def test_upload_then_inhouse_scan_identifies_and_prices_the_card(inhouse_client) -> None:  # noqa: ANN001
    upload = inhouse_client.post(
        "/captures",
        files=[("files", ("card.png", _rendered_card("Tidecaller Leviath", "8/120"), "image/png"))],
        headers=auth_header(),
    )
    assert upload.status_code == 201
    ref = upload.json()["ref"]

    scan = inhouse_client.post("/scan", json={"bundle_id": ref}, headers=auth_header())
    assert scan.status_code == 200
    body = scan.json()
    # The real recognizer read the real pixels and resolved the catalog card — then priced it.
    assert body["outcome"] == "resolved"
    assert body["card"]["identity"]["canonical_id"] == "origins-8"
    assert body["card"]["identity"]["name"] == "Tidecaller Leviath"
    assert body["card"]["price"] is not None
