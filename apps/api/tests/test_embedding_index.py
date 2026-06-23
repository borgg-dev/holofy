"""The embedding artwork index: cosine ranking, score calibration, and graceful loading.

No model here — the index operates on vectors. We feed known unit vectors and assert the nearest
neighbour, the cosine→base_score mapping the resolver ranks on, and that a missing or mismatched
on-disk pair loads as an empty index (so the provider falls back rather than crashing).
"""

from __future__ import annotations

import json

import numpy as np

from app.identify.embedding_index import (
    EmbeddingImageIndex,
    EmbeddingMatch,
    embeddings_path_for,
    load_embedding_index,
)
from app.identify.vision.embed import EMBED_DIM
from app.schemas.cards import CardIdentity, Variant


def _identity(cid: str) -> CardIdentity:
    return CardIdentity(
        canonical_id=cid, name=cid, set_name="Base Set",
        collector_number="4/102", language="en", variant=Variant.HOLO,
    )


def _unit(*vals: float) -> np.ndarray:
    v = np.zeros(EMBED_DIM, dtype=np.float32)
    for i, x in enumerate(vals):
        v[i] = x
    n = np.linalg.norm(v)
    return v / n if n else v


def test_query_ranks_by_cosine() -> None:
    ids = [_identity("a"), _identity("b"), _identity("c")]
    mat = np.stack([_unit(1, 0), _unit(0.9, 0.1), _unit(0, 1)])
    index = EmbeddingImageIndex(identities=ids, matrix=mat)

    matches = index.query(_unit(1, 0), k=3)

    assert [m.identity.canonical_id for m in matches] == ["a", "b", "c"]
    assert matches[0].cosine == 1.0
    assert matches[0].cosine > matches[1].cosine > matches[2].cosine


def test_empty_index_returns_no_matches() -> None:
    index = EmbeddingImageIndex(identities=[], matrix=np.zeros((0, EMBED_DIM), np.float32))
    assert index.query(_unit(1, 0), k=8) == []
    assert len(index) == 0


def test_base_score_calibration() -> None:
    # Distinct cards (~0.65) floor low; a clear match (~0.86) tops the band.
    assert EmbeddingMatch(_identity("x"), cosine=0.62).base_score == 0.0
    assert EmbeddingMatch(_identity("x"), cosine=0.86).base_score == 1.0
    mid = EmbeddingMatch(_identity("x"), cosine=0.74).base_score
    assert 0.45 < mid < 0.55


def test_load_missing_pair_is_empty(tmp_path) -> None:  # noqa: ANN001
    assert len(load_embedding_index(tmp_path / "nope.json")) == 0


def test_load_roundtrip(tmp_path) -> None:  # noqa: ANN001
    meta = tmp_path / "idx.json"
    cards = [
        {"canonical_id": "a", "name": "A", "set_name": "Base", "collector_number": "1/2",
         "language": "en", "variant": "holo", "image_url": None, "phash": "00"},
        {"canonical_id": "b", "name": "B", "set_name": "Base", "collector_number": "2/2",
         "language": "en", "variant": "holo", "image_url": None, "phash": "00"},
    ]
    meta.write_text(json.dumps({"locales": ["en"], "count": 2, "cards": cards}), encoding="utf-8")
    mat = np.stack([_unit(1, 0), _unit(0, 1)]).astype(np.float16)
    np.save(embeddings_path_for(meta), mat)

    index = load_embedding_index(meta)

    assert len(index) == 2
    assert index.query(_unit(0, 1), k=1)[0].identity.canonical_id == "b"


def test_load_length_mismatch_is_empty(tmp_path) -> None:  # noqa: ANN001
    # A metadata/vector row-count mismatch (a stale or half-written pair) must refuse, not
    # silently attribute every embedding to the wrong card.
    meta = tmp_path / "idx.json"
    cards = [{"canonical_id": "a", "name": "A", "set_name": "Base", "collector_number": "1/2",
              "language": "en", "variant": "holo", "image_url": None, "phash": "00"}]
    meta.write_text(json.dumps({"cards": cards}), encoding="utf-8")
    np.save(embeddings_path_for(meta), np.zeros((3, EMBED_DIM), np.float16))

    assert len(load_embedding_index(meta)) == 0
