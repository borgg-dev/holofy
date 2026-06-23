"""Replay real phone captures through both descriptors — the real-world sanity check.

The synthetic eval (eval_embedding.py) gives the generalizable accuracy number; this is the
qualitative counterpart on *actual* user captures (no ground-truth labels, so it reports what each
descriptor names, not a score). For every capture it rectifies once, then shows the embedding top-1
(card + cosine) beside the pHash top-1 (card + distance), plus the recognizer's commit/confirm
decision — so a human can eyeball whether the learned descriptor picks more plausible cards than
the hash did on the same hard, real images.

    PYTHONPATH=.deps:. python3.11 scripts/replay_captures.py --dir /tmp/real_captures \
        --index data/image_index.full.json --model data/recognition_model.onnx
"""

from __future__ import annotations

import argparse
import sys
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.identify.embedding_index import load_embedding_index  # noqa: E402
from app.identify.image_index import load_image_index  # noqa: E402
from app.identify.vision.embed import embed  # noqa: E402
from app.identify.vision.phash import phash  # noqa: E402
from app.identify.vision.rectify import rectify_card  # noqa: E402


def _best_embed(emb_index, image, model):  # noqa: ANN001
    best = None
    for k in range(4):
        cand = image if k == 0 else np.rot90(image, k)
        m = emb_index.query(embed(cand, model_path=model), k=1)
        if m and (best is None or m[0].cosine > best.cosine):
            best = m[0]
    return best


def _best_hash(hash_index, image):  # noqa: ANN001
    best = None
    for k in range(4):
        cand = image if k == 0 else np.rot90(image, k)
        m = hash_index.query(phash(cand), k=1)
        if m and (best is None or m[0].distance < best.distance):
            best = m[0]
    return best


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, default=Path("/tmp/real_captures"))
    ap.add_argument("--index", type=Path, default=Path("data/image_index.full.json"))
    ap.add_argument("--model", type=Path, default=Path("data/recognition_model.onnx"))
    ap.add_argument("--min-sim", type=float, default=0.70)
    args = ap.parse_args()

    emb_index = load_embedding_index(args.index)
    hash_index = load_image_index(args.index)
    print(f"index: {len(emb_index)} embeddings / {len(hash_index)} hashes\n")

    files = sorted(p for p in args.dir.rglob("*") if p.is_file())
    agree = emb_commit = 0
    for f in files:
        try:
            raw = f.read_bytes()
            Image.open(BytesIO(raw)).convert("RGB")  # validate it decodes
        except Exception:  # noqa: BLE001
            continue
        # rectify_card takes raw encoded bytes (it decodes + localizes internally), exactly as the
        # provider feeds it from the capture store.
        rect = rectify_card(raw)
        eb = _best_embed(emb_index, rect.image, str(args.model))
        hb = _best_hash(hash_index, rect.image)
        e_name = f"{eb.identity.name} [{eb.identity.collector_number}]" if eb else "—"
        h_name = f"{hb.identity.name} [{hb.identity.collector_number}]" if hb else "—"
        same = bool(eb and hb and eb.identity.canonical_id == hb.identity.canonical_id)
        agree += same
        committed = bool(eb and eb.cosine >= args.min_sim)
        emb_commit += committed
        flag = "✓commit" if committed else "·confirm/fallback"
        match = "=" if same else "≠"
        print(f"{f.parent.name[:10]}  EMB {eb.cosine:.3f} {e_name:<34} {match} pHASH d{hb.distance if hb else 0:<3} {h_name:<30} {flag}")

    print(f"\n{len(files)} captures · embedding committed {emb_commit} ({emb_commit / max(1, len(files)):.0%}) · "
          f"embedding/pHash agreed on {agree} ({agree / max(1, len(files)):.0%})")


if __name__ == "__main__":
    main()
