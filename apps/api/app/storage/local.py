"""Filesystem-backed capture storage — real uploaded bytes that survive a restart.

The local stand-in for EU-region object storage: each capture becomes a directory of its
stills under a configured root, addressed by an opaque hex reference. File I/O runs in a
worker thread so the event loop is never blocked on disk, mirroring how the async S3 client
that replaces this will behave behind the same ``CaptureStorage`` Protocol.
"""

from __future__ import annotations

import asyncio
import re
import secrets
from collections.abc import Sequence
from pathlib import Path

from app.storage.base import CaptureNotFoundError

# References are minted as 32-char hex (``token_hex(16)``); validating that shape before
# touching the filesystem both rejects an unresolvable ref early and forecloses any path
# traversal — a caller-supplied ref can never escape the storage root.
_REF_PATTERN = re.compile(r"\A[0-9a-f]{32}\Z")

# Stills are written zero-padded in capture order, so the primary frame is always ``000``.
_PRIMARY = "000"


class LocalCaptureStorage:
    """Stores each capture's stills as ``<root>/<ref>/<index>`` files on local disk."""

    def __init__(self, root: Path) -> None:
        self._root = root

    async def save(self, images: Sequence[bytes]) -> str:
        if not images:
            raise ValueError("a capture must carry at least one still")
        ref = secrets.token_hex(16)
        await asyncio.to_thread(self._write, ref, images)
        return ref

    async def load(self, capture_ref: str) -> bytes:
        if not _REF_PATTERN.match(capture_ref):
            raise CaptureNotFoundError(capture_ref)
        try:
            return await asyncio.to_thread((self._root / capture_ref / _PRIMARY).read_bytes)
        except FileNotFoundError as exc:
            raise CaptureNotFoundError(capture_ref) from exc

    async def delete(self, capture_ref: str) -> None:
        # Idempotent erasure: a malformed or already-gone ref is a no-op. The shape check also
        # forecloses path traversal, exactly as on load — a caller ref can't escape the root.
        if not _REF_PATTERN.match(capture_ref):
            return
        await asyncio.to_thread(self._remove, capture_ref)

    def _write(self, ref: str, images: Sequence[bytes]) -> None:
        directory = self._root / ref
        directory.mkdir(parents=True, exist_ok=True)
        for index, image in enumerate(images):
            (directory / f"{index:03d}").write_bytes(image)

    def _remove(self, ref: str) -> None:
        directory = self._root / ref
        if not directory.is_dir():
            return
        for child in directory.iterdir():
            child.unlink(missing_ok=True)
        directory.rmdir()
