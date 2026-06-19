"""Capture object storage — the write side of the seam recognition and pre-grade read.

Stills are uploaded once, land here, and are thereafter addressed by an opaque reference
(``bundle_id`` for a scan, ``capture_ref`` for a pre-grade) — never carried as bytes through
the API (data minimization, architecture §6). This is the EU-region object-store seam: the
mock synthesises captures by reference (``app.grading.capture_store``), the dev backends keep
real uploaded bytes (in process or on disk), and an S3/GCS client drops in behind the same
Protocol with no change at the call sites.

``CaptureNotFoundError`` lives here because storage is where a reference is resolved (or
isn't); the pre-grade and scan layers re-raise it as their own 404 envelope.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable


class CaptureNotFoundError(Exception):
    """A capture reference resolved to nothing — an unknown or expired upload."""


@runtime_checkable
class CaptureStorage(Protocol):
    """Persists a capture's stills and resolves a reference back to bytes.

    A capture is one or more stills shot together (a single scan frame, or the multi-angle
    bundle a pre-grade needs). ``save`` returns the reference the scan/pre-grade calls then
    pass; ``load`` returns the *primary* still — the one a single-frame measurement reads —
    so today's consumers (centering) need not know how many angles were captured.
    """

    async def save(self, images: Sequence[bytes]) -> str:
        """Persist a capture's stills together and return the reference that resolves them."""
        ...

    async def load(self, capture_ref: str) -> bytes:
        """Return the primary still's bytes for a reference, or raise ``CaptureNotFoundError``."""
        ...
