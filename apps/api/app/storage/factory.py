"""Capture-storage selection by configuration.

The one place that decides which implementation backs the capture seam, mirroring
``app.providers.factory``. ``mock`` keeps the synthetic-by-reference store the pre-grade
tests drive; ``memory`` and ``local`` keep real uploaded bytes for dev; an EU-region S3/GCS
backend drops in here behind the same Protocol. The explicit ``case _`` raises on an
unwired enum value rather than silently returning ``None``.
"""

from __future__ import annotations

from pathlib import Path

from app.config import CaptureStorageBackend, Settings
from app.grading.capture_store import CaptureStore, MockCaptureStore
from app.storage.local import LocalCaptureStorage
from app.storage.memory import InMemoryCaptureStorage


def build_capture_store(settings: Settings) -> CaptureStore:
    match settings.capture_storage:
        case CaptureStorageBackend.MOCK:
            return MockCaptureStore()
        case CaptureStorageBackend.MEMORY:
            return InMemoryCaptureStorage()
        case CaptureStorageBackend.LOCAL:
            return LocalCaptureStorage(Path(settings.capture_storage_dir))
        case unknown:  # pragma: no cover - guards an unwired enum value
            raise ValueError(f"unsupported capture storage backend: {unknown}")
