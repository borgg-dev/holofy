"""The visual-first recognition provider's routing: artwork match vs text fallback.

The artwork index and OCR reader are fakes here — the point is the orchestration contract: an
empty index is a transparent pass-through; a confident artwork hit is resolved visually; a
nearest hit beyond the match cutoff (card not in the index) defers to the text fallback; and an
unresolvable capture recognizes nothing rather than erroring.
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

import numpy as np
import pytest
from PIL import Image

from app.identify.catalog import CardRead
from app.identify.embedding_index import EmbeddingMatch
from app.identify.image_index import ImageMatch
from app.identify.vision.embed import EmbeddingModelUnavailable
from app.identify.visual_provider import VisualRecognitionProvider
from app.identify.visual_resolver import VisualCardResolver
from app.schemas.cards import CardIdentity, RecognitionCandidate, RecognitionResult, Variant
from app.storage.memory import InMemoryCaptureStorage


@dataclass(frozen=True, slots=True)
class _Bundle:
    bundle_id: str
    image_count: int = 1


def _png() -> bytes:
    buf = BytesIO()
    Image.fromarray(np.full((200, 140, 3), 220, np.uint8)).save(buf, format="PNG")
    return buf.getvalue()


def _identity(canonical_id: str) -> CardIdentity:
    return CardIdentity(
        canonical_id=canonical_id, name="Charizard", set_name="Base Set",
        collector_number="4/102", language="en", variant=Variant.HOLO,
    )


class _FakeIndex:
    def __init__(self, matches: list[ImageMatch], size: int = 100) -> None:
        self._matches = matches
        self._size = size

    def query(self, image_hash: int, *, k: int = 8) -> list[ImageMatch]:  # noqa: ARG002
        return self._matches[:k]

    def __len__(self) -> int:
        return self._size


class _FakeReader:
    def __init__(self, read: CardRead) -> None:
        self._read = read
        self.called = False

    async def read_image(self, image, quality, *, fallback_bytes=None):  # noqa: ANN001, ARG002
        self.called = True
        return self._read


class _FakeFallback:
    def __init__(self, result: RecognitionResult) -> None:
        self._result = result
        self.calls = 0

    async def recognize(self, bundle) -> RecognitionResult:  # noqa: ANN001, ARG002
        self.calls += 1
        return self._result


_SENTINEL = RecognitionResult(
    candidates=[RecognitionCandidate(identity=_identity("from-fallback"), confidence=0.5)]
)


def _provider(store, index, reader, fallback, *, max_distance=14) -> VisualRecognitionProvider:
    return VisualRecognitionProvider(
        store=store, reader=reader, image_index=index,
        visual_resolver=VisualCardResolver(), fallback=fallback, max_match_distance=max_distance,
    )


@pytest.mark.asyncio
async def test_empty_index_passes_through_to_fallback() -> None:
    store = InMemoryCaptureStorage()
    ref = await store.save([_png()])
    reader = _FakeReader(CardRead(name="Charizard"))
    fallback = _FakeFallback(_SENTINEL)
    provider = _provider(store, _FakeIndex([], size=0), reader, fallback)

    result = await provider.recognize(_Bundle(bundle_id=ref))

    assert result is _SENTINEL
    assert fallback.calls == 1
    assert not reader.called  # never rectified/hashed — pure pass-through


@pytest.mark.asyncio
async def test_confident_artwork_hit_resolves_visually() -> None:
    store = InMemoryCaptureStorage()
    ref = await store.save([_png()])
    matches = [ImageMatch(_identity("base1-4"), distance=3), ImageMatch(_identity("base1-9"), distance=18)]
    reader = _FakeReader(CardRead(name="Charizard"))
    fallback = _FakeFallback(_SENTINEL)
    provider = _provider(store, _FakeIndex(matches), reader, fallback)

    result = await provider.recognize(_Bundle(bundle_id=ref))

    assert result.candidates[0].identity.canonical_id == "base1-4"
    assert fallback.calls == 0
    assert reader.called


@pytest.mark.asyncio
async def test_nearest_hit_beyond_cutoff_defers_to_fallback() -> None:
    store = InMemoryCaptureStorage()
    ref = await store.save([_png()])
    # Card not in the index → even the nearest art sits far away.
    matches = [ImageMatch(_identity("unrelated"), distance=22)]
    reader = _FakeReader(CardRead(name="Charizard"))
    fallback = _FakeFallback(_SENTINEL)
    provider = _provider(store, _FakeIndex(matches), reader, fallback, max_distance=14)

    result = await provider.recognize(_Bundle(bundle_id=ref))

    assert result is _SENTINEL
    assert fallback.calls == 1


@pytest.mark.asyncio
async def test_unresolvable_capture_recognizes_nothing() -> None:
    store = InMemoryCaptureStorage()
    matches = [ImageMatch(_identity("base1-4"), distance=3)]
    provider = _provider(store, _FakeIndex(matches), _FakeReader(CardRead()), _FakeFallback(_SENTINEL))

    result = await provider.recognize(_Bundle(bundle_id="never-uploaded"))

    assert result.candidates == []


# --- Embedding tier (primary) ------------------------------------------------------------------
# The embedding model is faked: the provider's only contract with it is "embed the crop, query the
# embedding index, abstain below the cosine cutoff." We stub the embed() call and a cosine index so
# the routing — embedding hit vs miss-to-hash vs model-unavailable — is what's under test.


class _FakeEmbeddingIndex:
    def __init__(self, matches: list[EmbeddingMatch], size: int = 100) -> None:
        self._matches = matches
        self._size = size

    def query(self, vector, *, k: int = 8):  # noqa: ANN001, ARG002
        return self._matches[:k]

    def __len__(self) -> int:
        return self._size


def _embed_provider(store, embedding_index, reader, fallback, *, hash_index=None, min_similarity=0.70):
    return VisualRecognitionProvider(
        store=store,
        reader=reader,
        image_index=hash_index if hash_index is not None else _FakeIndex([], size=0),
        visual_resolver=VisualCardResolver(),
        fallback=fallback,
        embedding_index=embedding_index,
        model_path="fake-model.onnx",
        min_similarity=min_similarity,
    )


def test_merge_matches_keeps_anchored_below_higher_cosine_neighbours() -> None:
    # The whole point of the OCR anchor: a card the OCR identified must survive the merge even when
    # the (wrong) embedding nearest-neighbours all out-cosine it — else it never reaches the resolver.
    from app.identify.embedding_index import EmbeddingMatch
    from app.identify.visual_provider import _merge_matches

    embedding = [EmbeddingMatch(_identity(f"wrong-{i}"), cosine=0.78 - i * 0.01) for i in range(8)]
    anchored = [EmbeddingMatch(_identity("the-right-card"), cosine=0.72)]

    merged = _merge_matches(embedding, anchored)

    assert any(m.identity.canonical_id == "the-right-card" for m in merged), "anchored card was culled"
    assert len(merged) <= 8


@pytest.mark.asyncio
async def test_embedding_hit_resolves(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr("app.identify.visual_provider.embed", lambda img, *, model_path: np.zeros(384, np.float32))
    store = InMemoryCaptureStorage()
    ref = await store.save([_png()])
    matches = [EmbeddingMatch(_identity("base1-4"), cosine=0.86), EmbeddingMatch(_identity("base1-9"), cosine=0.66)]
    fallback = _FakeFallback(_SENTINEL)
    provider = _embed_provider(store, _FakeEmbeddingIndex(matches), _FakeReader(CardRead(name="Charizard")), fallback)

    result = await provider.recognize(_Bundle(bundle_id=ref))

    assert result.candidates[0].identity.canonical_id == "base1-4"
    assert fallback.calls == 0


@pytest.mark.asyncio
async def test_embedding_miss_falls_through_to_hash(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr("app.identify.visual_provider.embed", lambda img, *, model_path: np.zeros(384, np.float32))
    store = InMemoryCaptureStorage()
    ref = await store.save([_png()])
    # Embedding's nearest sits below the cosine cutoff → abstain to the hash tier, which has a hit.
    emb = _FakeEmbeddingIndex([EmbeddingMatch(_identity("unrelated"), cosine=0.61)])
    hash_hit = _FakeIndex([ImageMatch(_identity("base1-4"), distance=3)])
    fallback = _FakeFallback(_SENTINEL)
    provider = _embed_provider(store, emb, _FakeReader(CardRead(name="Charizard")), fallback, hash_index=hash_hit)

    result = await provider.recognize(_Bundle(bundle_id=ref))

    assert result.candidates[0].identity.canonical_id == "base1-4"
    assert fallback.calls == 0


@pytest.mark.asyncio
async def test_embedding_model_unavailable_falls_back(monkeypatch) -> None:  # noqa: ANN001
    def _boom(img, *, model_path):  # noqa: ANN001, ARG001
        raise EmbeddingModelUnavailable("no model")

    monkeypatch.setattr("app.identify.visual_provider.embed", _boom)
    store = InMemoryCaptureStorage()
    ref = await store.save([_png()])
    emb = _FakeEmbeddingIndex([EmbeddingMatch(_identity("base1-4"), cosine=0.9)])
    fallback = _FakeFallback(_SENTINEL)
    # No hash index → a model that won't load defers all the way to the text fallback.
    provider = _embed_provider(store, emb, _FakeReader(CardRead(name="Charizard")), fallback)

    result = await provider.recognize(_Bundle(bundle_id=ref))

    assert result is _SENTINEL
    assert fallback.calls == 1
