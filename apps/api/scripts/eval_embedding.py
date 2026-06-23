"""Measure recognition accuracy at catalog scale — the generalizable, not-overfit number.

The review's non-negotiable: you cannot claim "high accuracy" without a number, and the number
must generalize, not be tuned to a handful of example cards. This samples cards from across the
*whole* built index, renders each through a battery of realistic phone-capture degradations
(perspective warp, blur, glare, brightness/contrast jitter, rotation, downscale, JPEG recompress),
and measures — over hundreds of independent cards — how often the recognizer names the right one.

It reports, head-to-head, both descriptors on the *same* degraded images:
  • EMBEDDING top-1 / top-5 identity recall   (the new primary path)
  • pHASH     top-1 / top-5 identity recall    (the prior path, for the delta)
and the cosine distribution of the true match vs the best wrong match, which calibrates
``recognition_visual_min_similarity`` and the cosine floor/ceil.

    PYTHONPATH=.deps:. python3.11 scripts/eval_embedding.py --index data/image_index.full.json \
        --model data/recognition_model.onnx --sample 300 --variants 2
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from io import BytesIO
from pathlib import Path

import httpx
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.identify.embedding_index import load_embedding_index  # noqa: E402
from app.identify.image_index import load_image_index  # noqa: E402
from app.identify.vision.embed import embed  # noqa: E402
from app.identify.vision.phash import hamming_distance, phash  # noqa: E402


def _identity_key(canonical_id: str, cards_by_id: dict) -> str:
    """Identity truth = name+number family, so a correct artwork match on any reprint counts.
    Falls back to the id itself when metadata is absent."""
    row = cards_by_id.get(canonical_id)
    if not row:
        return canonical_id
    return f"{row['name']}|{row['collector_number']}".lower()


def _perspective(img: Image.Image, rng: random.Random) -> Image.Image:
    """A mild homography — the card photographed at a glancing angle, not flat-on."""
    w, h = img.size
    m = 0.10
    dx = lambda: rng.uniform(-m, m) * w  # noqa: E731
    dy = lambda: rng.uniform(-m, m) * h  # noqa: E731
    src = [(0, 0), (w, 0), (w, h), (0, h)]
    dst = [(dx(), dy()), (w + dx(), dy()), (w + dx(), h + dy()), (dx(), h + dy())]
    # Solve for the 8 PIL perspective coefficients mapping dst→src.
    a = []
    b = []
    for (x, y), (X, Y) in zip(src, dst):
        a.append([X, Y, 1, 0, 0, 0, -x * X, -x * Y])
        a.append([0, 0, 0, X, Y, 1, -y * X, -y * Y])
        b += [x, y]
    coeffs = np.linalg.solve(np.array(a, dtype=float), np.array(b, dtype=float))
    return img.transform((w, h), Image.PERSPECTIVE, data=coeffs, resample=Image.BICUBIC)


def _glare(img: Image.Image, rng: random.Random) -> Image.Image:
    """A soft bright blob — phone flash / window reflection on the foil."""
    w, h = img.size
    yy, xx = np.mgrid[0:h, 0:w]
    cx, cy = rng.uniform(0.2, 0.8) * w, rng.uniform(0.2, 0.8) * h
    r = rng.uniform(0.2, 0.4) * min(w, h)
    blob = np.clip(1.0 - ((xx - cx) ** 2 + (yy - cy) ** 2) / (r * r), 0, 1)
    arr = np.asarray(img).astype(np.float32)
    arr += (blob[..., None] * rng.uniform(40, 110)).astype(np.float32)
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def _degrade(img: Image.Image, rng: random.Random) -> np.ndarray:
    """One realistic phone capture of the card: angle, glare, blur, exposure, scale, JPEG."""
    img = img.convert("RGB")
    if rng.random() < 0.85:
        img = _perspective(img, rng)
    img = img.rotate(rng.uniform(-7, 7), resample=Image.BICUBIC, fillcolor=(20, 20, 22))
    if rng.random() < 0.6:
        img = _glare(img, rng)
    img = ImageEnhance.Brightness(img).enhance(rng.uniform(0.7, 1.15))
    img = ImageEnhance.Contrast(img).enhance(rng.uniform(0.8, 1.15))
    img = img.filter(ImageFilter.GaussianBlur(rng.uniform(0.6, 1.8)))
    scale = rng.uniform(0.35, 0.7)
    small = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))))
    buf = BytesIO()
    small.save(buf, format="JPEG", quality=rng.randint(55, 80))
    return np.asarray(Image.open(BytesIO(buf.getvalue())).convert("RGB"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", type=Path, default=Path("data/image_index.full.json"))
    ap.add_argument("--model", type=Path, default=Path("data/recognition_model.onnx"))
    ap.add_argument("--sample", type=int, default=300)
    ap.add_argument("--variants", type=int, default=2)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    rows = json.loads(args.index.read_text(encoding="utf-8"))["cards"]
    cards_by_id = {r["canonical_id"]: r for r in rows}
    emb_index = load_embedding_index(args.index)
    hash_index = load_image_index(args.index)
    print(f"index: {len(emb_index)} embeddings / {len(hash_index)} hashes")

    sample = rng.sample(rows, min(args.sample, len(rows)))
    n = emb_top1 = emb_top5 = hash_top1 = hash_top5 = 0
    true_cos: list[float] = []
    wrong_cos: list[float] = []

    with httpx.Client(timeout=30) as client:
        for i, card in enumerate(sample):
            url = card.get("image_url")
            if not url:
                continue
            try:
                resp = client.get(url)
                resp.raise_for_status()
                base = Image.open(BytesIO(resp.content)).convert("RGB")
            except Exception:  # noqa: BLE001
                continue
            truth = _identity_key(card["canonical_id"], cards_by_id)
            for _ in range(args.variants):
                arr = _degrade(base, rng)
                n += 1
                # Embedding ranking.
                vec = embed(arr, model_path=str(args.model))
                em = emb_index.query(vec, k=5)
                em_keys = [_identity_key(m.identity.canonical_id, cards_by_id) for m in em]
                if em_keys and em_keys[0] == truth:
                    emb_top1 += 1
                if truth in em_keys:
                    emb_top5 += 1
                # Calibration signal: cosine of the true match vs the best wrong match.
                t = next((m.cosine for m, k in zip(em, em_keys) if k == truth), None)
                w = next((m.cosine for m, k in zip(em, em_keys) if k != truth), None)
                if t is not None:
                    true_cos.append(t)
                if w is not None:
                    wrong_cos.append(w)
                # pHash ranking on the same image.
                h = phash(arr)
                hm = sorted(hash_index.entries, key=lambda e: hamming_distance(h, e.phash))[:5]
                hm_keys = [_identity_key(e.identity.canonical_id, cards_by_id) for e in hm]
                if hm_keys and hm_keys[0] == truth:
                    hash_top1 += 1
                if truth in hm_keys:
                    hash_top5 += 1
            if (i + 1) % 25 == 0:
                print(f"  {i + 1}/{len(sample)} cards, {n} queries…")

    print(f"\n=== {n} degraded queries over {len(sample)} sampled cards ===")
    print(f"EMBEDDING  top-1 {emb_top1 / n:6.1%}   top-5 {emb_top5 / n:6.1%}")
    print(f"pHASH      top-1 {hash_top1 / n:6.1%}   top-5 {hash_top5 / n:6.1%}")
    if true_cos and wrong_cos:
        tc = np.array(true_cos)
        wc = np.array(wrong_cos)
        print(f"\ntrue-match cosine : p05={np.percentile(tc, 5):.3f}  p50={np.percentile(tc, 50):.3f}  mean={tc.mean():.3f}")
        print(f"wrong-match cosine: p50={np.percentile(wc, 50):.3f}  p95={np.percentile(wc, 95):.3f}  max={wc.max():.3f}")
        print(f"suggested min_similarity ≈ {max(np.percentile(tc, 10), np.percentile(wc, 90)):.3f}")


if __name__ == "__main__":
    main()
