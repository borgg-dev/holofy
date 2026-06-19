"""Capture storage backends — the in-memory and on-disk stores that hold real uploaded
bytes. Covers the save→load roundtrip, multi-still primary selection, the unresolvable
reference, and (for the filesystem store) that a crafted reference can't escape the root.
"""

from __future__ import annotations

import pytest

from app.storage.base import CaptureNotFoundError
from app.storage.local import LocalCaptureStorage
from app.storage.memory import InMemoryCaptureStorage


@pytest.mark.asyncio
async def test_memory_store_roundtrips_the_primary_still() -> None:
    store = InMemoryCaptureStorage()
    ref = await store.save([b"front-bytes", b"back-bytes"])

    # load returns the primary (first) still — what a single-frame measurement reads.
    assert await store.load(ref) == b"front-bytes"


@pytest.mark.asyncio
async def test_memory_store_unknown_reference_raises_not_found() -> None:
    store = InMemoryCaptureStorage()
    with pytest.raises(CaptureNotFoundError):
        await store.load("never-saved")


@pytest.mark.asyncio
async def test_memory_store_rejects_an_empty_capture() -> None:
    store = InMemoryCaptureStorage()
    with pytest.raises(ValueError):
        await store.save([])


@pytest.mark.asyncio
async def test_local_store_persists_stills_to_disk(tmp_path) -> None:  # noqa: ANN001
    store = LocalCaptureStorage(tmp_path)
    ref = await store.save([b"front-bytes", b"back-bytes"])

    assert await store.load(ref) == b"front-bytes"
    # Both stills are written, capture order preserved, so multi-angle grading can read them.
    assert sorted(p.name for p in (tmp_path / ref).iterdir()) == ["000", "001"]


@pytest.mark.asyncio
async def test_local_store_unknown_reference_raises_not_found(tmp_path) -> None:  # noqa: ANN001
    store = LocalCaptureStorage(tmp_path)
    # A well-formed 32-hex ref that was never written still resolves to nothing.
    with pytest.raises(CaptureNotFoundError):
        await store.load("0" * 32)


@pytest.mark.asyncio
async def test_local_store_rejects_a_traversal_reference(tmp_path) -> None:  # noqa: ANN001
    # A ref that isn't the minted hex shape is refused before any path is touched, so
    # ``..``-style traversal can never read outside the storage root.
    store = LocalCaptureStorage(tmp_path)
    with pytest.raises(CaptureNotFoundError):
        await store.load("../../etc/passwd")


@pytest.mark.asyncio
async def test_memory_store_delete_erases_and_is_idempotent() -> None:
    store = InMemoryCaptureStorage()
    ref = await store.save([b"front-bytes"])
    await store.delete(ref)
    with pytest.raises(CaptureNotFoundError):
        await store.load(ref)
    # Idempotent: deleting an already-gone (or never-known) ref is a no-op, not an error.
    await store.delete(ref)
    await store.delete("never-saved")


@pytest.mark.asyncio
async def test_local_store_delete_removes_files_and_is_idempotent(tmp_path) -> None:  # noqa: ANN001
    store = LocalCaptureStorage(tmp_path)
    ref = await store.save([b"front-bytes", b"back-bytes"])
    await store.delete(ref)
    with pytest.raises(CaptureNotFoundError):
        await store.load(ref)
    assert not (tmp_path / ref).exists()
    # Idempotent, and a malformed ref can't escape the root or raise.
    await store.delete(ref)
    await store.delete("../../etc/passwd")
