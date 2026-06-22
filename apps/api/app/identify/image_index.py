"""The artwork match index — recognize a card by its picture, nearest-neighbour over pHashes.

This is the primary identity signal the review called for: every catalog printing is reduced
once to a 64-bit perceptual hash of its official artwork (built offline by
``scripts/build_image_index.py``); at scan time the rectified card's hash is matched against
the index by Hamming distance, and the nearest printings come back ranked. Unlike the
text-only path, this resolves a card whose tiny collector number never OCR'd — the art alone
identifies it — and it cannot confuse two visually different cards that happen to share a name.

``ImageMatchIndex`` is a Protocol so the in-memory linear scan here (fine for the Pokémon
catalog — tens of thousands of 64-bit popcounts per query is sub-millisecond) is swappable for
a BK-tree / vector index later without touching the resolver. The on-disk form is a plain JSON
file so the index is a build artefact the API loads at startup, not a service dependency.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.identify.vision.phash import hamming_distance
from app.schemas.cards import CardIdentity, Variant


@dataclass(frozen=True, slots=True)
class ImageMatch:
    """One artwork hit: the catalog identity and how far its hash sat from the query (0–64)."""

    identity: CardIdentity
    distance: int

    @property
    def similarity(self) -> float:
        return 1.0 - self.distance / 64.0


@dataclass(frozen=True, slots=True)
class ImageHashEntry:
    """A catalog printing fingerprinted by its artwork — the unit the index stores and ranks."""

    identity: CardIdentity
    phash: int


class ImageMatchIndex(Protocol):
    def query(self, image_hash: int, *, k: int = 8) -> list[ImageMatch]:
        """Return up to ``k`` catalog printings nearest the query hash, closest first."""
        ...

    def __len__(self) -> int: ...


@dataclass
class InMemoryImageIndex:
    """Linear-scan artwork index over fingerprinted catalog entries."""

    entries: Sequence[ImageHashEntry]

    def query(self, image_hash: int, *, k: int = 8) -> list[ImageMatch]:
        if not self.entries:
            return []
        scored = (
            ImageMatch(identity=entry.identity, distance=hamming_distance(image_hash, entry.phash))
            for entry in self.entries
        )
        return sorted(scored, key=lambda m: m.distance)[:k]

    def __len__(self) -> int:
        return len(self.entries)


def load_image_index(path: str | Path) -> InMemoryImageIndex:
    """Load a built index from its JSON artefact. A missing/empty file is an empty index — the
    provider falls back to the text path rather than failing, so an undeployed index degrades
    gracefully to the prior behaviour."""
    p = Path(path)
    if not p.exists():
        return InMemoryImageIndex(entries=())
    raw = json.loads(p.read_text(encoding="utf-8"))
    return InMemoryImageIndex(entries=tuple(_entry_from_dict(row) for row in raw.get("cards", [])))


def _entry_from_dict(row: dict) -> ImageHashEntry:
    return ImageHashEntry(
        identity=CardIdentity(
            canonical_id=row["canonical_id"],
            name=row["name"],
            set_name=row["set_name"],
            collector_number=row["collector_number"],
            language=row.get("language", "en"),
            variant=Variant(row.get("variant", "holo")),
            image_url=row.get("image_url"),
        ),
        # Stored as a hex string so the 64-bit value survives JSON round-trips losslessly.
        phash=int(row["phash"], 16),
    )


def entry_to_dict(entry: ImageHashEntry) -> dict:
    """Serialize one entry for the on-disk index (inverse of ``_entry_from_dict``)."""
    identity = entry.identity
    return {
        "canonical_id": identity.canonical_id,
        "name": identity.name,
        "set_name": identity.set_name,
        "collector_number": identity.collector_number,
        "language": identity.language,
        "variant": identity.variant.value,
        "image_url": identity.image_url,
        "phash": format(entry.phash, "016x"),
    }
