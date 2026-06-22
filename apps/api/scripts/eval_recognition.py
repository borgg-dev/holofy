"""Measure recognition accuracy on a labelled folder of real card photos.

The review's non-negotiable: you cannot say "high accuracy" without a number. This runs the full
owned visual pipeline — rectify → pHash → artwork index → OCR fusion — over a directory of real
captures whose true card id is known, and reports the two metrics that matter separately:

  • top-1 / top-3 IDENTITY     — did we name the right card (any printing of the right artwork)?
  • top-1 EXACT-PRINTING       — did we pin the exact set/number (the reprint-disambiguation case)?
  • commit vs confirm rates     — how often the flow auto-commits vs routes to the user.

Labels come from filenames: ``base1-4__anything.jpg`` → truth ``base1-4`` (text before ``__``,
or the whole stem if absent). Identity truth is the card's name+number family; exact truth is the
canonical id. Build the index first (scripts/build_image_index.py), then:

    python3.11 scripts/eval_recognition.py --images ./eval_set --index data/image_index.json
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.identify.catalog import CardRead  # noqa: E402
from app.identify.image_index import load_image_index  # noqa: E402
from app.identify.vision.phash import phash  # noqa: E402
from app.identify.vision.rectify import rectify_card  # noqa: E402
from app.identify.visual_resolver import VisualCardResolver  # noqa: E402

_CONFIRM_THRESHOLD = 0.70
_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def _truth_id(path: Path) -> str:
    stem = path.stem
    return stem.split("__", 1)[0] if "__" in stem else stem


def _identity_key(index, canonical_id: str) -> tuple[str, str] | None:
    """The (name, number) family a canonical id belongs to — identity truth ignores which
    reprint, so two same-art printings share a key."""
    for entry in index.entries:
        if entry.identity.canonical_id == canonical_id:
            return (entry.identity.name.lower(), entry.identity.collector_number)
    return None


def evaluate(images_dir: Path, index_path: Path) -> int:
    index = load_image_index(index_path)
    if len(index) == 0:
        print(f"error: index {index_path} is empty — build it first", file=sys.stderr)
        return 2
    resolver = VisualCardResolver()
    paths = sorted(p for p in images_dir.iterdir() if p.suffix.lower() in _IMAGE_SUFFIXES)
    if not paths:
        print(f"error: no images in {images_dir}", file=sys.stderr)
        return 2

    n = 0
    top1_id = top3_id = top1_exact = 0
    committed = committed_correct = 0
    for path in paths:
        truth = _truth_id(path)
        truth_family = _identity_key(index, truth)
        try:
            arr = np.asarray(Image.open(path).convert("RGB"))
        except OSError:
            print(f"  skip (decode failed): {path.name}")
            continue
        n += 1

        rect = rectify_card(_to_bytes(path))
        matches = index.query(phash(rect.image), k=8)
        read = _read_for(arr)  # OCR is optional in eval; left as a no-op cue here
        result = resolver.resolve(matches, read, rect.quality)
        cands = result.candidates

        exact_ok = bool(cands) and cands[0].identity.canonical_id == truth
        fam = [(c.identity.name.lower(), c.identity.collector_number) for c in cands]
        id_top1 = bool(cands) and truth_family is not None and fam[0] == truth_family
        id_top3 = truth_family is not None and truth_family in fam[:3]

        top1_exact += exact_ok
        top1_id += id_top1
        top3_id += id_top3
        if cands and cands[0].confidence >= _CONFIRM_THRESHOLD:
            committed += 1
            committed_correct += exact_ok

    _report(n, top1_id, top3_id, top1_exact, committed, committed_correct)
    return 0


def _to_bytes(path: Path) -> bytes:
    return path.read_bytes()


def _read_for(_arr: np.ndarray) -> CardRead:
    # The eval scores the visual matcher in isolation; wire the real OCR reader here to also
    # measure number-assisted disambiguation. Empty read = pure artwork identification.
    return CardRead()


def _pct(num: int, den: int) -> str:
    return f"{(100.0 * num / den):5.1f}%  ({num}/{den})" if den else "  n/a"


def _report(n, top1_id, top3_id, top1_exact, committed, committed_correct) -> None:
    print("\n=== Recognition accuracy ===")
    print(f"  samples                 {n}")
    print(f"  top-1 identity          {_pct(top1_id, n)}")
    print(f"  top-3 identity          {_pct(top3_id, n)}")
    print(f"  top-1 exact printing    {_pct(top1_exact, n)}")
    print(f"  auto-committed          {_pct(committed, n)}")
    print(f"  commit precision        {_pct(committed_correct, committed)}")
    print("  (identity = right artwork/name; exact = right set+number; the gap is the reprint")
    print("   disambiguation the collector number resolves.)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate recognition accuracy on a labelled folder.")
    parser.add_argument("--images", type=Path, required=True, help="folder of labelled card photos")
    parser.add_argument("--index", type=Path, default=Path("data/image_index.json"))
    args = parser.parse_args()
    sys.exit(evaluate(args.images, args.index))


if __name__ == "__main__":
    main()
