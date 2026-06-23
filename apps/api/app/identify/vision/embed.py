"""Runtime image embedding — the primary recognition descriptor.

A card is identified by the *embedding* of its picture: a 384-d vector from DINOv2 (small),
whose self-supervised features are state-of-the-art for instance / near-duplicate retrieval —
exactly "which *exact* printing is this card?". Unlike the perceptual hash this replaces, the
embedding is learned, so it stays robust across the lighting, blur, glare and angle of a real
phone capture where a hash (a downsampled DCT of pixels) degrades fast.

The model is exported once to ONNX (``scripts/export_recognition_model.py``) and served here with
onnxruntime alone — no torch/transformers in the API image or the hot path. Preprocessing is
reproduced in numpy/Pillow so the offline index builder and the online query share one transform
without sharing the torch pipeline; if the two diverged, the stored catalog vectors and the query
vector would live in different spaces and every match would be wrong.

The session is a lazily-built, cached singleton (ONNX load is ~100ms, inference ~30–60ms/CPU).
A missing model file raises ``EmbeddingModelUnavailable`` so the provider can fall back to the
hash/text path rather than crash — shipping the model is a deploy step, not a hard dependency.
"""

from __future__ import annotations

import threading
from pathlib import Path

import numpy as np
from PIL import Image

# DINOv2 patch-14 at 224 → 16×16 patches. Must match the export resolution exactly.
_INPUT_SIZE = 224
# ImageNet statistics DINOv2 was trained with; the normalization is part of the model's input
# contract, not a tunable.
_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32).reshape(3, 1, 1)
_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32).reshape(3, 1, 1)

# The embedding dimensionality — asserted against the loaded model so a swapped/corrupt artifact
# fails loud at startup rather than silently producing wrong-width vectors.
EMBED_DIM = 384


class EmbeddingModelUnavailable(RuntimeError):
    """The ONNX model isn't present/loadable — callers fall back to the non-embedding path."""


_lock = threading.Lock()
_session: object | None = None
_session_path: str | None = None


def _load_session(model_path: str):
    """Build (or reuse) the cached onnxruntime session for ``model_path``."""
    global _session, _session_path
    with _lock:
        if _session is not None and _session_path == model_path:
            return _session
        if not Path(model_path).exists():
            raise EmbeddingModelUnavailable(f"recognition model not found at {model_path}")
        try:
            import onnxruntime as ort
        except ImportError as exc:  # pragma: no cover - import guard
            raise EmbeddingModelUnavailable("onnxruntime not installed") from exc
        opts = ort.SessionOptions()
        # Recognition runs one image at a time on request; a single intra-op thread keeps it from
        # contending with the API's request workers under load.
        opts.intra_op_num_threads = 1
        opts.inter_op_num_threads = 1
        sess = ort.InferenceSession(model_path, sess_options=opts, providers=["CPUExecutionProvider"])
        out_dim = sess.get_outputs()[0].shape[-1]
        if isinstance(out_dim, int) and out_dim != EMBED_DIM:
            raise EmbeddingModelUnavailable(f"model emits dim {out_dim}, expected {EMBED_DIM}")
        _session = sess
        _session_path = model_path
        return sess


def _preprocess(image: np.ndarray) -> np.ndarray:
    """RGB uint8 HxWx3 → normalized NCHW float32 the model expects.

    The whole card is resized to 224×224 (no crop): both the catalog art and the query crop go
    through this identical squash, so the model sees consistent geometry and the full card — name,
    artwork, set symbol and collector number all inform the descriptor.
    """
    if image.ndim == 2:
        image = np.stack([image] * 3, axis=-1)
    if image.shape[-1] == 4:
        image = image[..., :3]
    pil = Image.fromarray(image.astype(np.uint8), mode="RGB").resize(
        (_INPUT_SIZE, _INPUT_SIZE), Image.BICUBIC
    )
    arr = np.asarray(pil, dtype=np.float32) / 255.0  # HWC, 0..1
    chw = np.transpose(arr, (2, 0, 1))  # CHW
    chw = (chw - _MEAN) / _STD
    return chw[np.newaxis, ...]  # NCHW


def _run(session, batch: np.ndarray) -> np.ndarray:
    out = session.run(["embedding"], {"pixel_values": batch.astype(np.float32)})[0]
    # The graph L2-normalizes, but re-normalize defensively so cosine == dot downstream.
    norms = np.linalg.norm(out, axis=1, keepdims=True)
    return (out / np.clip(norms, 1e-12, None)).astype(np.float32)


def embed(image: np.ndarray, *, model_path: str) -> np.ndarray:
    """Embed one RGB image into a unit-length 384-d vector. Raises if the model is unavailable."""
    session = _load_session(model_path)
    return _run(session, _preprocess(image))[0]


def embed_batch(images: list[np.ndarray], *, model_path: str) -> np.ndarray:
    """Embed many RGB images at once → an (N, 384) unit-length matrix. Used by the index builder."""
    session = _load_session(model_path)
    if not images:
        return np.zeros((0, EMBED_DIM), dtype=np.float32)
    batch = np.concatenate([_preprocess(im) for im in images], axis=0)
    return _run(session, batch)
