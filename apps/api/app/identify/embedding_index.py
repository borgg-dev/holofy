"""The artwork embedding index — recognize a card by nearest catalog *embedding*.

The primary identity signal (it supersedes the perceptual-hash index for capability, while that
hash index stays as a graceful fallback). Every catalog printing is reduced once to a 384-d
DINOv2 embedding of its picture (built offline by ``scripts/build_image_index.py``); at scan time
the rectified card is embedded and matched by cosine similarity. Because the descriptor is learned
rather than a downsampled DCT, it stays discriminative across the lighting, blur and angle of a
real phone capture — the regime where the hash collided.

The vectors are stored unit-length, so cosine is a single matrix–vector product: at tens of
thousands of rows this is sub-millisecond in numpy, and the linear scan stays behind the same
``query`` shape as the hash index so a vector database can drop in later untouched. The on-disk
form is a metadata JSON (the catalog identities, shared with the hash index) plus a compact
float16 ``.npy`` of the matrix, aligned row-for-row — a build artefact the API memory-maps at
startup, never a service dependency.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from app.identify.image_index import _entry_from_dict
from app.identify.vision.embed import EMBED_DIM
from app.schemas.cards import CardIdentity

# Cosine → base score. Calibrated to the model's observed distribution: distinct cards sit around
# ~0.65 even when superficially alike, a true match (even degraded) clears ~0.78, and identical
# art tops ~0.9. The floor/ceil map that band onto 0–1 so the resolver's OCR boosts and thresholds
# stay in the same score space as the hash path. Re-tune against the real-capture eval set.
_COS_FLOOR = 0.62
_COS_CEIL = 0.86


def _cos_to_score(cosine: float) -> float:
    return max(0.0, min(1.0, (cosine - _COS_FLOOR) / (_COS_CEIL - _COS_FLOOR)))


@dataclass(frozen=True, slots=True)
class EmbeddingMatch:
    """One embedding hit: the catalog identity and the cosine similarity to the query (−1..1)."""

    identity: CardIdentity
    cosine: float

    @property
    def base_score(self) -> float:
        """The descriptor-neutral 0–1 confidence the resolver ranks on (calibrated cosine)."""
        return _cos_to_score(self.cosine)


@dataclass
class EmbeddingImageIndex:
    """Linear-scan cosine index over unit-length catalog embeddings."""

    identities: list[CardIdentity]
    # (N, EMBED_DIM) float32, every row L2-normalized — cosine is then a plain dot product.
    matrix: np.ndarray

    def reference(self, canonical_id: str) -> np.ndarray | None:
        """The catalog reference embedding for a specific card — the genuine artwork a capture is
        compared against for the authenticity reference check. Keyed by canonical id (any indexed
        language; the artwork embeds near-identically across EN/FR). ``None`` if not in the index."""
        if not hasattr(self, "_by_canonical"):
            self._by_canonical: dict[str, int] = {}
            for i, identity in enumerate(self.identities):
                self._by_canonical.setdefault(identity.canonical_id, i)
        row = self._by_canonical.get(canonical_id)
        return None if row is None else self.matrix[row]

    def query(self, vector: np.ndarray, *, k: int = 8) -> list[EmbeddingMatch]:
        if self.matrix.shape[0] == 0:
            return []
        sims = self.matrix @ vector.astype(np.float32)
        k = min(k, sims.shape[0])
        # argpartition for the top-k, then sort just those — avoids a full 40k sort per query.
        top = np.argpartition(-sims, k - 1)[:k]
        top = top[np.argsort(-sims[top])]
        return [EmbeddingMatch(identity=self.identities[i], cosine=float(sims[i])) for i in top]

    def __len__(self) -> int:
        return self.matrix.shape[0]


def embeddings_path_for(index_path: str | Path) -> Path:
    """The sidecar matrix path that pairs with a metadata index JSON (``…/image_index.f16.npy``)."""
    p = Path(index_path)
    return p.with_suffix(".f16.npy")


def load_embedding_index(
    index_path: str | Path, embeddings_path: str | Path | None = None
) -> EmbeddingImageIndex:
    """Load the embedding index from its metadata JSON + sidecar matrix. A missing/mismatched pair
    is an empty index — the provider falls back to the hash/text path rather than failing, so an
    undeployed embedding artefact degrades gracefully to the prior behaviour."""
    import json

    meta = Path(index_path)
    vecs = Path(embeddings_path) if embeddings_path else embeddings_path_for(index_path)
    if not meta.exists() or not vecs.exists():
        return EmbeddingImageIndex(identities=[], matrix=np.zeros((0, EMBED_DIM), dtype=np.float32))

    rows = json.loads(meta.read_text(encoding="utf-8")).get("cards", [])
    matrix = np.load(vecs).astype(np.float32)
    # The matrix is row-aligned to the metadata; a length mismatch means a stale/half-written pair,
    # which we refuse rather than mis-attribute every embedding to the wrong card.
    if matrix.shape[0] != len(rows) or (matrix.size and matrix.shape[1] != EMBED_DIM):
        return EmbeddingImageIndex(identities=[], matrix=np.zeros((0, EMBED_DIM), dtype=np.float32))
    # Re-normalize defensively (float16 storage perturbs unit length slightly).
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    matrix = matrix / np.clip(norms, 1e-12, None)
    identities = [_entry_from_dict(row).identity for row in rows]
    return EmbeddingImageIndex(identities=identities, matrix=matrix.astype(np.float32))
