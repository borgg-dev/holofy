"""In-process capture storage — real uploaded bytes, no disk, no network.

The dev/smoke backend: an actual upload→scan→pre-grade journey runs against bytes the user
sent (unlike the synthetic ``MockCaptureStore``), but nothing is persisted past process
exit. Single-process only — it backs ``make api-smoke`` and local runs, not a fleet.
"""

from __future__ import annotations

import secrets
from collections.abc import Sequence

from app.storage.base import CaptureNotFoundError


class InMemoryCaptureStorage:
    """Keeps each capture's stills in a dict keyed on a freshly minted opaque reference."""

    def __init__(self) -> None:
        self._captures: dict[str, list[bytes]] = {}

    async def save(self, images: Sequence[bytes]) -> str:
        if not images:
            raise ValueError("a capture must carry at least one still")
        ref = secrets.token_hex(16)
        self._captures[ref] = list(images)
        return ref

    async def load(self, capture_ref: str) -> bytes:
        try:
            return self._captures[capture_ref][0]
        except KeyError as exc:
            raise CaptureNotFoundError(capture_ref) from exc

    async def delete(self, capture_ref: str) -> None:
        # Idempotent erasure: drop the stills if present, no-op if already gone.
        self._captures.pop(capture_ref, None)
