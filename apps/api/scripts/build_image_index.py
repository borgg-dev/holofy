"""Build the artwork match index from TCGdex — the recognition database.

Pulls catalog printings (their official card artwork), reduces each to a 64-bit perceptual
hash, and writes the JSON index that ``app.identify.image_index`` loads at startup. This is the
offline half of the visual recognizer: run it to (re)build the database; the API never computes
catalog hashes on the hot path.

Real, no key required (TCGdex is open). Bounded by default to a curated set list so a build is
quick and verifiable; pass ``--all`` to fingerprint the whole catalog, or ``--sets a b c`` for
specific sets.

    python3.11 scripts/build_image_index.py --out data/image_index.json --sets base1 base2
    python3.11 scripts/build_image_index.py --out data/image_index.json --all

Reads are concurrent but politely capped. Images that 404 or won't decode are skipped with a
logged warning rather than failing the whole build — a few missing arts must not block the index.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from io import BytesIO
from pathlib import Path

import httpx
import numpy as np
from PIL import Image

# Run from apps/api with PYTHONPATH=.deps:. — make the app package importable when invoked
# directly as a script too.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.identify.embedding_index import embeddings_path_for  # noqa: E402
from app.identify.image_index import ImageHashEntry, entry_to_dict  # noqa: E402
from app.identify.tcgdex_catalog import (  # noqa: E402
    _collector_number,
    _image_url,
    _primary_variant,
)
from app.identify.vision.embed import EMBED_DIM, embed  # noqa: E402
from app.identify.vision.phash import phash  # noqa: E402
from app.schemas.cards import CardIdentity  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("build_image_index")

_API_ROOT = "https://api.tcgdex.net/v2"
# A small, high-value default: the cards beta users actually scan. Enough to validate the whole
# pipeline end-to-end without a multi-hour full-catalog crawl.
_DEFAULT_SETS = ("base1", "base2", "base3", "base4", "base5")
# Concurrency is the build's main throughput lever. TCGdex is a CDN-backed open API that tolerates
# parallel reads, so we run well above a timid 8 — but with bounded retry/backoff (below) so the
# extra load can't silently *drop* cards on a transient 429/timeout, which would quietly shrink the
# index. phash is CPU work and runs in a thread, so downloads and hashing overlap.
_CONCURRENCY = 24
# Transient failures (429 rate-limit, connection reset, slow image) must be retried, not skipped —
# a skipped card is a hole in the recognition index. Only give up after this many attempts.
_MAX_ATTEMPTS = 4


async def _get_with_retry(client: httpx.AsyncClient, url: str) -> httpx.Response | None:
    """GET with bounded exponential backoff. Returns the response, or None after exhausting tries."""
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp
        except httpx.HTTPError as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            # 404 is a real "this art doesn't exist" — never worth retrying. Everything else
            # (429/5xx/timeouts/resets) is transient: back off and try again.
            if status == 404 or attempt == _MAX_ATTEMPTS:
                log.warning("skip (fetch failed after %d): %s — %s", attempt, url, exc)
                return None
            await asyncio.sleep(0.5 * 2 ** (attempt - 1))
    return None


async def _get_json(client: httpx.AsyncClient, url: str) -> object | None:
    resp = await _get_with_retry(client, url)
    return resp.json() if resp is not None else None


async def _list_set_ids(client: httpx.AsyncClient, locale: str, *, all_sets: bool, sets: list[str]) -> list[str]:
    if not all_sets:
        return sets
    payload = await _get_json(client, f"{_API_ROOT}/{locale}/sets")
    return [s["id"] for s in payload or [] if s.get("id")]


async def _set_card_ids(client: httpx.AsyncClient, locale: str, set_id: str) -> list[str]:
    payload = await _get_json(client, f"{_API_ROOT}/{locale}/sets/{set_id}")
    cards = (payload or {}).get("cards", []) if isinstance(payload, dict) else []
    return [c["id"] for c in cards if c.get("id")]


async def _fingerprint_card(
    client: httpx.AsyncClient, locale: str, card_id: str, sem: asyncio.Semaphore, model_path: str
) -> tuple[ImageHashEntry, "np.ndarray"] | None:
    async with sem:
        card = await _get_json(client, f"{_API_ROOT}/{locale}/cards/{card_id}")
        if not isinstance(card, dict):
            return None
        image_url = _image_url(card)
        if not image_url:
            log.warning("skip (no image): %s", card_id)
            return None
        img_resp = await _get_with_retry(client, image_url)
        if img_resp is None:
            return None
        try:
            arr = np.asarray(Image.open(BytesIO(img_resp.content)).convert("RGB"))
        except OSError as exc:
            log.warning("skip (image decode failed): %s — %s", card_id, exc)
            return None

        number_str = _collector_number(card)
        # phash and the DINOv2 embedding are both CPU-heavy; run them off the event loop so they
        # overlap the many in-flight downloads instead of serializing the crawl behind compute.
        # The embedding is the primary descriptor (the .npy sidecar); the hash stays as a fallback.
        card_phash, vector = await asyncio.gather(
            asyncio.to_thread(phash, arr),
            asyncio.to_thread(embed, arr, model_path=model_path),
        )
        entry = ImageHashEntry(
            identity=CardIdentity(
                canonical_id=card["id"],
                name=card["name"],
                set_name=(card.get("set") or {}).get("name", ""),
                collector_number=number_str,
                language=locale,
                variant=_primary_variant(card),
                image_url=image_url,
            ),
            phash=card_phash,
        )
        return entry, vector


async def _build_locale(
    client: httpx.AsyncClient, locale: str, *, all_sets: bool, sets: list[str], model_path: str
) -> list[tuple[ImageHashEntry, "np.ndarray"]]:
    set_ids = await _list_set_ids(client, locale, all_sets=all_sets, sets=sets)
    log.info("fingerprinting %d set(s) in locale %s", len(set_ids), locale)

    card_ids: list[str] = []
    for set_id in set_ids:
        ids = await _set_card_ids(client, locale, set_id)
        log.info("  [%s] %s: %d cards", locale, set_id, len(ids))
        card_ids.extend(ids)

    sem = asyncio.Semaphore(_CONCURRENCY)
    results = await asyncio.gather(
        *(_fingerprint_card(client, locale, cid, sem, model_path) for cid in card_ids)
    )
    return [r for r in results if r is not None]


async def build(out: Path, locales: list[str], *, all_sets: bool, sets: list[str], model_path: str) -> int:
    # A card is printed per language — a French Charizard is "Dracaufeu" with French text, so its
    # picture embeds/hashes differently from the English print. We fingerprint each locale and union
    # the entries (keyed by id+language) so a card photographed in any configured language matches.
    seen: set[tuple[str, str]] = set()
    entries: list[ImageHashEntry] = []
    vectors: list["np.ndarray"] = []
    limits = httpx.Limits(max_connections=_CONCURRENCY * 2, max_keepalive_connections=_CONCURRENCY)
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0), limits=limits) as client:
        for locale in locales:
            for entry, vector in await _build_locale(
                client, locale, all_sets=all_sets, sets=sets, model_path=model_path
            ):
                key = (entry.identity.canonical_id, entry.identity.language)
                if key not in seen:
                    seen.add(key)
                    entries.append(entry)
                    vectors.append(vector)

    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {"locales": locales, "count": len(entries), "cards": [entry_to_dict(e) for e in entries]}
    out.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    # The embedding matrix, row-aligned to ``cards`` and stored float16 (half the bytes, negligible
    # cosine error). This sidecar is the primary recognition descriptor; the JSON's phash is fallback.
    matrix = (
        np.stack(vectors).astype(np.float16)
        if vectors
        else np.zeros((0, EMBED_DIM), dtype=np.float16)
    )
    vec_path = embeddings_path_for(out)
    np.save(vec_path, matrix)
    log.info("wrote %d fingerprints + %s embeddings across %s → %s, %s", len(entries), matrix.shape, locales, out, vec_path)
    return len(entries)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the TCGdex artwork pHash index.")
    parser.add_argument("--out", type=Path, default=Path("data/image_index.json"))
    # Match the recognizer's configured locales (HOLOFY_TCGDEX_RECOGNITION_LOCALES): English +
    # French cover the two largest Latin-script communities the OCR/art match reads today.
    parser.add_argument("--locales", nargs="+", default=["en", "fr"])
    parser.add_argument("--all", action="store_true", help="fingerprint every set (slow)")
    parser.add_argument("--sets", nargs="*", default=list(_DEFAULT_SETS))
    parser.add_argument(
        "--model",
        type=Path,
        default=Path("data/recognition_model.onnx"),
        help="the exported DINOv2 ONNX model used for the embedding sidecar",
    )
    args = parser.parse_args()
    count = asyncio.run(
        build(args.out, args.locales, all_sets=args.all, sets=args.sets, model_path=str(args.model))
    )
    if count == 0:
        log.error("no fingerprints written — check connectivity / set ids")
        sys.exit(1)


if __name__ == "__main__":
    main()
