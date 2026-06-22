"""The artwork match index: nearest-neighbour ranking and JSON round-trip.

Pure and offline — fixed hashes, no images or network. Asserts the index ranks by Hamming
distance and that an entry survives the on-disk serialization the builder writes and the API
loads.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.identify.image_index import (
    ImageHashEntry,
    InMemoryImageIndex,
    entry_to_dict,
    load_image_index,
)
from app.schemas.cards import CardIdentity, Variant


def _entry(canonical_id: str, phash: int) -> ImageHashEntry:
    return ImageHashEntry(
        identity=CardIdentity(
            canonical_id=canonical_id,
            name="Charizard",
            set_name="Base Set",
            collector_number="4/102",
            language="en",
            variant=Variant.HOLO,
            image_url="https://example/card.webp",
        ),
        phash=phash,
    )


def test_query_ranks_by_hamming_distance() -> None:
    index = InMemoryImageIndex(
        entries=(
            _entry("near", 0b1011),
            _entry("far", 0b0100_1011),
            _entry("exact", 0b1010),
        )
    )
    matches = index.query(0b1010, k=3)
    assert [m.identity.canonical_id for m in matches] == ["exact", "near", "far"]
    assert matches[0].distance == 0
    assert matches[0].similarity == 1.0


def test_query_caps_at_k() -> None:
    index = InMemoryImageIndex(entries=tuple(_entry(str(i), i) for i in range(20)))
    assert len(index.query(0, k=5)) == 5


def test_empty_index_returns_no_matches() -> None:
    assert InMemoryImageIndex(entries=()).query(123, k=8) == []
    assert len(InMemoryImageIndex(entries=())) == 0


def test_json_round_trip_preserves_entry(tmp_path: Path) -> None:
    entry = _entry("base1-4", 0xABCDEF0123456789)
    path = tmp_path / "index.json"
    path.write_text(json.dumps({"cards": [entry_to_dict(entry)]}), encoding="utf-8")

    loaded = load_image_index(path)
    assert len(loaded) == 1
    back = loaded.entries[0]
    assert back.phash == entry.phash
    assert back.identity.canonical_id == "base1-4"
    assert back.identity.collector_number == "4/102"
    assert back.identity.variant is Variant.HOLO


def test_missing_index_file_is_empty(tmp_path: Path) -> None:
    assert len(load_image_index(tmp_path / "does-not-exist.json")) == 0
