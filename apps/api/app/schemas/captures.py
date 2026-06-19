"""Response contract for the capture-upload endpoint.

Upload is the step that turns stills into the reference the scan and pre-grade calls carry.
The client uploads once, gets back a ``ref`` plus the ``image_count`` the server actually
stored, and passes that ref as the ``bundle_id`` (scan) or ``capture_ref`` (pre-grade) —
the bytes never travel with those later requests.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class CaptureUploadResponse(BaseModel):
    ref: str = Field(description="Opaque reference the scan/pre-grade calls pass back.")
    image_count: int = Field(ge=1, description="Number of stills stored for this capture.")
