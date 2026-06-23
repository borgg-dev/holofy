"""Export the recognition embedding model to ONNX — the one-time build step.

The runtime recognizer identifies a card by the *embedding* of its picture, nearest-neighbour
over the catalog. That embedding comes from DINOv2 (small) — a self-supervised vision model whose
features are state-of-the-art for instance / near-duplicate retrieval, which is exactly the task
("which *exact* printing is this card?"). DINOv2 beats CLIP here because CLIP's features are
semantic/category-level ("a Pokémon card") where DINOv2's are instance-level ("*this* artwork").

This script downloads the pretrained weights once and exports the image encoder to ONNX so the
API serves it with onnxruntime alone (no torch/transformers in the hot path or the prod image).
The exported graph takes a preprocessed NCHW float tensor and returns the L2-normalized CLS
embedding (384-d). Preprocessing (resize→normalize) is reproduced in numpy in the runtime module
``app.identify.vision.embed`` so the two sides agree without sharing the torch transform.

    .embed-build/bin/python scripts/export_recognition_model.py --out data/recognition_model.onnx

Run from apps/api. Needs the build venv (torch + transformers + onnx). One-time; the ONNX file is
the deploy artefact (mounted alongside the index like a data file, not committed to git).
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import torch
from transformers import AutoModel

_MODEL_ID = "facebook/dinov2-small"
_INPUT_SIZE = 224  # DINOv2 patch-14 at 224 → 16×16 patches; the standard inference resolution.


class _Encoder(torch.nn.Module):
    """Wrap DINOv2 to emit a single L2-normalized embedding per image (the CLS token).

    Folding the normalization into the graph means the runtime does a bare matmul for cosine —
    every stored catalog vector and every query vector is already unit-length.
    """

    def __init__(self) -> None:
        super().__init__()
        self.backbone = AutoModel.from_pretrained(_MODEL_ID)
        self.backbone.eval()

    def forward(self, pixel_values: torch.Tensor) -> torch.Tensor:
        out = self.backbone(pixel_values=pixel_values)
        cls = out.last_hidden_state[:, 0]  # CLS token — the global image descriptor.
        return torch.nn.functional.normalize(cls, p=2, dim=1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export DINOv2-small image encoder to ONNX.")
    parser.add_argument("--out", type=Path, default=Path("data/recognition_model.onnx"))
    args = parser.parse_args()

    model = _Encoder()
    model.eval()

    dummy = torch.randn(1, 3, _INPUT_SIZE, _INPUT_SIZE)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with torch.no_grad():
        torch.onnx.export(
            model,
            (dummy,),
            str(args.out),
            input_names=["pixel_values"],
            output_names=["embedding"],
            dynamic_axes={"pixel_values": {0: "batch"}, "embedding": {0: "batch"}},
            opset_version=17,
            do_constant_folding=True,
            # The legacy TorchScript exporter is far more robust on transformer graphs than the
            # new torch.export/dynamo path, which trips on DINOv2's attention. Pin it explicitly.
            dynamo=False,
        )

    # Parity check: the exported ONNX must match the torch reference within float tolerance, or the
    # offline-built index and the online query would live in subtly different embedding spaces.
    import onnxruntime as ort

    with torch.no_grad():
        ref = model(dummy).numpy()
    sess = ort.InferenceSession(str(args.out), providers=["CPUExecutionProvider"])
    got = sess.run(["embedding"], {"pixel_values": dummy.numpy()})[0]
    max_err = float(np.abs(ref - got).max())
    cos = float((ref[0] * got[0]).sum())
    print(f"exported {args.out}  dim={got.shape[1]}  parity max_err={max_err:.2e}  cos={cos:.6f}")
    if max_err > 1e-3:
        raise SystemExit(f"ONNX parity check failed (max_err={max_err:.2e})")


if __name__ == "__main__":
    main()
