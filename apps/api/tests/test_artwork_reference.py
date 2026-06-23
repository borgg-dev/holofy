"""The artwork-reference authenticity signal — its safe, reassurance-only contract.

The CONSISTENT path needs the real embedding model (exercised in the de-risk/eval scripts, not the
unit suite); here we pin the honest degradations: no reference, no bytes, or no model all yield an
``unreadable`` ``artwork_match`` signal — never an error, and never an accusatory ``deviation``.
Plus the index's reference lookup the signal depends on.
"""

from __future__ import annotations

import numpy as np

from app.authenticity.artwork_reference import assess_artwork_match
from app.identify.embedding_index import EmbeddingImageIndex
from app.identify.vision.embed import EMBED_DIM
from app.schemas.authenticity import SignalKind, SignalObservation
from app.schemas.cards import CardIdentity, Variant


def _identity(cid: str) -> CardIdentity:
    return CardIdentity(
        canonical_id=cid, name=cid, set_name="Base", collector_number="1/1",
        language="en", variant=Variant.HOLO,
    )


def test_no_reference_is_unreadable() -> None:
    sig = assess_artwork_match(b"some-bytes", None, model_path="data/recognition_model.onnx")
    assert sig.kind is SignalKind.ARTWORK_MATCH
    assert sig.observation is SignalObservation.UNREADABLE


def test_no_bytes_is_unreadable() -> None:
    ref = np.zeros(EMBED_DIM, dtype=np.float32)
    sig = assess_artwork_match(b"", ref, model_path="data/recognition_model.onnx")
    assert sig.observation is SignalObservation.UNREADABLE


def test_missing_model_is_unreadable_not_error() -> None:
    # A real reference + bytes but no model must degrade to "couldn't compare", never raise.
    ref = np.zeros(EMBED_DIM, dtype=np.float32)
    sig = assess_artwork_match(b"\x89PNG-not-really", ref, model_path="/no/such/model.onnx")
    assert sig.observation is SignalObservation.UNREADABLE


def test_index_reference_lookup() -> None:
    ids = [_identity("a"), _identity("b")]
    mat = np.stack([np.full(EMBED_DIM, 0.1, np.float32), np.full(EMBED_DIM, 0.2, np.float32)])
    index = EmbeddingImageIndex(identities=ids, matrix=mat)

    assert index.reference("a") is not None
    assert abs(float(index.reference("b")[0]) - 0.2) < 1e-6
    assert index.reference("missing") is None
