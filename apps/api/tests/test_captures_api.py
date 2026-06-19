"""API coverage for /captures — the upload step that turns camera stills into the reference
the scan and pre-grade calls carry. Runs against the in-memory storage backend (real bytes,
no disk) so the full upload→pre-grade journey is exercised on bytes the client actually
sent, and the ingress guards (auth, content type, count) are checked at the edge.
"""

from __future__ import annotations

from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.config import (
    AuthBackend,
    CaptureStorageBackend,
    PricingBackend,
    RecognitionBackend,
    Settings,
)
from app.db.base import Base
from app.main import create_app
from tests.conftest import auth_header

_DEV_SECRET = "test-secret"


def _png_bytes(color: int = 200) -> bytes:
    buffer = BytesIO()
    Image.new("L", (64, 64), color).save(buffer, format="PNG")
    return buffer.getvalue()


def _file(name: str = "front.png") -> tuple[str, tuple[str, bytes, str]]:
    return ("files", (name, _png_bytes(), "image/png"))


@pytest.fixture
def memory_client():
    # Real uploaded bytes kept in process — unlike the synthetic default store, so an upload
    # actually resolves on a later /pregrade.
    settings = Settings(
        auth_provider=AuthBackend.DEV_TOKEN,
        recognition_provider=RecognitionBackend.MOCK,
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


def test_upload_requires_authentication(memory_client) -> None:  # noqa: ANN001
    response = memory_client.post("/captures", files=[_file()])

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


def test_upload_returns_a_reference_and_count(memory_client) -> None:  # noqa: ANN001
    response = memory_client.post(
        "/captures", files=[_file("front.png"), _file("back.png")], headers=auth_header()
    )

    assert response.status_code == 201
    body = response.json()
    assert body["image_count"] == 2
    assert body["ref"]


def test_uploaded_capture_resolves_on_a_later_pregrade(memory_client) -> None:  # noqa: ANN001
    # The whole point of the seam: a ref from /captures is a real capture /pregrade can load.
    ref = memory_client.post(
        "/captures", files=[_file()], headers=auth_header()
    ).json()["ref"]

    response = memory_client.post(
        "/pregrade", json={"capture_ref": ref}, headers=auth_header()
    )

    # It resolved to real bytes (not a 404) and produced a typed pre-grade outcome.
    assert response.status_code == 200
    assert response.json()["status"] in {"estimated", "retake"}


def test_upload_rejects_a_non_image(memory_client) -> None:  # noqa: ANN001
    response = memory_client.post(
        "/captures",
        files=[("files", ("notes.txt", b"hello", "text/plain"))],
        headers=auth_header(),
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "capture_rejected"


def test_upload_rejects_non_image_bytes_lying_about_content_type(memory_client) -> None:  # noqa: ANN001
    # A client claiming image/png but sending non-image bytes is rejected by the magic-byte
    # check — the declared content-type is never trusted to decide what gets stored.
    response = memory_client.post(
        "/captures",
        files=[("files", ("fake.png", b"this is definitely not a PNG", "image/png"))],
        headers=auth_header(),
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "capture_rejected"


def test_upload_rejects_too_many_images(memory_client) -> None:  # noqa: ANN001
    response = memory_client.post(
        "/captures", files=[_file() for _ in range(9)], headers=auth_header()
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "capture_rejected"


def test_upload_is_unavailable_on_the_synthetic_store(client) -> None:  # noqa: ANN001
    # The default conftest client uses the mock (synthetic) store, which can't accept bytes —
    # the endpoint must say so cleanly rather than failing deep in.
    response = client.post("/captures", files=[_file()], headers=auth_header())

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "capture_upload_unavailable"
