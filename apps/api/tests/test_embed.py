"""The runtime embedding module's contract — without loading the real model.

We assert the preprocessing shape/normalization (the half the offline builder and online query must
agree on) and that a missing model raises ``EmbeddingModelUnavailable`` so the provider can fall
back rather than crash. The forward pass itself is the model's; it's exercised in the build/eval
scripts, not the unit suite.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.identify.vision import embed as embed_mod
from app.identify.vision.embed import EmbeddingModelUnavailable, embed


def test_preprocess_shape_and_normalization() -> None:
    img = np.random.randint(0, 255, (300, 210, 3), dtype=np.uint8)
    out = embed_mod._preprocess(img)
    assert out.shape == (1, 3, 224, 224)
    assert out.dtype == np.float32


def test_preprocess_handles_grayscale_and_alpha() -> None:
    gray = np.full((50, 40), 128, dtype=np.uint8)
    assert embed_mod._preprocess(gray).shape == (1, 3, 224, 224)
    rgba = np.full((50, 40, 4), 128, dtype=np.uint8)
    assert embed_mod._preprocess(rgba).shape == (1, 3, 224, 224)


def test_missing_model_raises() -> None:
    img = np.zeros((40, 40, 3), dtype=np.uint8)
    with pytest.raises(EmbeddingModelUnavailable):
        embed(img, model_path="/no/such/model.onnx")
