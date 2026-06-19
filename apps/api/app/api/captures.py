"""Capture-upload endpoint — stills in, a reference out.

The first step of every real scan and pre-grade: the client posts the camera stills here,
the server stores them in object storage, and returns the opaque reference the subsequent
``/scan`` or ``/pregrade`` call carries. Splitting upload from those calls keeps image bytes
out of the recognition/grading requests (data minimization, §6) and lets the multi-angle
pre-grade reuse one stored capture.

User-scoped — captures are personal data, so the bearer token is required. Ingress is
guarded before any byte is written: too many stills, an oversized still, or a non-image
content type is rejected up front so storage COGS and the decode path stay bounded.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile, status

from app.api.dependencies import get_capture_storage, get_current_user, get_settings
from app.config import Settings
from app.core.errors import CaptureRejectedError
from app.db.models import User
from app.schemas.captures import CaptureUploadResponse
from app.storage.base import CaptureStorage

router = APIRouter(tags=["captures"])

# Phone cameras emit JPEG; PNG/WebP cover screenshots and the web client. HEIC is excluded
# until the decode path (Pillow) gains a plugin, so we never store bytes we can't read back.
_ALLOWED_CONTENT_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})


def _sniff_image_type(data: bytes) -> str | None:
    """Identify an image from its magic bytes — the authoritative check, since a client's
    declared content-type can lie. Returns the format name, or ``None`` if the bytes are not
    one of the formats we accept (so a renamed PDF/script can't be stored as an 'image')."""
    if data[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


@router.post(
    "/captures", response_model=CaptureUploadResponse, status_code=status.HTTP_201_CREATED
)
async def upload_capture(
    files: list[UploadFile] = File(..., description="One or more stills of a single card."),
    user: User = Depends(get_current_user),
    storage: CaptureStorage = Depends(get_capture_storage),
    settings: Settings = Depends(get_settings),
) -> CaptureUploadResponse:
    if not files:
        raise CaptureRejectedError("A capture needs at least one image.")
    if len(files) > settings.capture_max_images:
        raise CaptureRejectedError(
            "Too many images for one capture.",
            details={"limit": settings.capture_max_images, "received": len(files)},
        )

    images: list[bytes] = []
    for upload in files:
        if upload.content_type not in _ALLOWED_CONTENT_TYPES:
            raise CaptureRejectedError(
                "Capture images must be JPEG, PNG, or WebP.",
                details={"content_type": upload.content_type or "unknown"},
            )
        data = await upload.read()
        if not data:
            raise CaptureRejectedError("A capture image was empty.")
        if len(data) > settings.capture_max_image_bytes:
            raise CaptureRejectedError(
                "A capture image is too large.",
                details={"limit_bytes": settings.capture_max_image_bytes},
            )
        # The declared content-type is a hint; the magic bytes are the truth. Reject anything
        # that isn't actually a JPEG/PNG/WebP so we never store (or later decode) spoofed bytes.
        if _sniff_image_type(data) is None:
            raise CaptureRejectedError(
                "Capture images must be real JPEG, PNG, or WebP files.",
                details={"declared_content_type": upload.content_type or "unknown"},
            )
        images.append(data)

    ref = await storage.save(images)
    return CaptureUploadResponse(ref=ref, image_count=len(images))
