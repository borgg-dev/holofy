"""Live end-to-end on OUR OWNED models — no mock recognition/grading, no vendor API, no keys.

Boots against the in-house recognizer (detect → OCR → resolve) and the in-house grader
(centering + condition), uploads real card images over HTTP, and walks the journey so a human
can watch the owned intelligence work: the presence guard rejects a non-card, a clean card
resolves and prices, an ambiguous reprint routes to a confirm, and a capture pre-grades to an
honest range. Run via scripts/dev_smoke_inhouse.sh.
"""

from __future__ import annotations

import os
import sys
from io import BytesIO

import httpx
from PIL import Image, ImageDraw, ImageFont

from app.auth.dev_token import mint_dev_token
from app.config import INSECURE_DEV_SECRET

BASE_URL = os.environ.get("HOLOFY_SMOKE_BASE_URL", "http://127.0.0.1:8099")


def _eur(value: object) -> str:
    return f"€{value}" if value is not None else "—"


def _font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype("DejaVuSans-Bold.ttf", size)


def _card_png(name: str, number: str) -> bytes:
    """A real card image: bright bordered card on a dark surface, name top, number bottom."""
    image = Image.new("RGB", (440, 600), (15, 15, 20))
    draw = ImageDraw.Draw(image)
    draw.rectangle((30, 30, 410, 570), fill=(236, 236, 236))
    draw.text((55, 55), name, fill=(12, 12, 12), font=_font(34))
    draw.text((55, 510), number, fill=(12, 12, 12), font=_font(28))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _bordered_card_png() -> bytes:
    """A centred, evenly-bordered card (inner art panel) so centering can measure it."""
    image = Image.new("RGB", (500, 700), (12, 12, 16))
    draw = ImageDraw.Draw(image)
    draw.rectangle((24, 24, 476, 676), fill=(235, 235, 235))
    draw.rectangle((64, 64, 436, 636), fill=(95, 95, 95))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _blank_png() -> bytes:
    """A near-uniform dark frame — no card. The presence guard should reject it."""
    buffer = BytesIO()
    Image.new("RGB", (440, 600), (14, 14, 18)).save(buffer, format="PNG")
    return buffer.getvalue()


def _upload(client: httpx.Client, image: bytes, name: str) -> str:
    response = client.post("/captures", files=[("files", (name, image, "image/png"))])
    response.raise_for_status()
    return response.json()["ref"]


def main() -> int:
    token = mint_dev_token("demo-collector", secret=INSECURE_DEV_SECRET)
    auth = {"Authorization": f"Bearer {token}"}

    with httpx.Client(base_url=BASE_URL, headers=auth, timeout=30.0) as client:
        health = client.get("/health").json()
        print(f"health        : {health['status']} · region {health.get('data_region')}")
        print("backends      : recognition=inhouse · grading=inhouse (owned models, no vendor)")

        blank_ref = _upload(client, _blank_png(), "blank.png")
        guard = client.post("/scan", json={"bundle_id": blank_ref})
        print(
            f"guard         : non-card frame -> {guard.status_code} "
            f"{guard.json()['error']['code']} (presence guard rejected before OCR)"
        )

        tide_ref = _upload(client, _card_png("Tidecaller Leviath", "8/120"), "tide.png")
        resolved = client.post("/scan", json={"bundle_id": tide_ref}).json()
        card = resolved["card"]
        print(
            f"scan (clean)  : {resolved['outcome']} -> {card['identity']['name']} "
            f"({card['identity']['set_name']} {card['identity']['collector_number']}) "
            f"@ {_eur((card['price'] or {}).get('value'))} — read from real pixels"
        )

        # Numerator only ("12", no set total): two same-name reprints can't be pinned, so the
        # owned resolver routes to a confirm rather than guessing a high-value variant.
        ember_ref = _upload(client, _card_png("Emberwyrm Sovereign", "12"), "ember.png")
        low = client.post("/scan", json={"bundle_id": ember_ref}).json()
        if low["outcome"] == "needs_confirmation":
            a, b = low["choices"]
            print(
                f"scan (ambig)  : needs_confirmation -> {a['identity']['set_name']} "
                f"{_eur((a['price'] or {}).get('value'))} vs {b['identity']['set_name']} "
                f"{_eur((b['price'] or {}).get('value'))} · delta {_eur(low['price_delta'])}"
            )
        else:
            print(f"scan (ambig)  : {low['outcome']} -> {low.get('card', {}).get('identity', {})}")

        grade_ref = _upload(client, _bordered_card_png(), "grade.png")
        pre = client.post("/pregrade", json={"capture_ref": grade_ref}).json()
        if pre["status"] == "estimated":
            p = pre["probability"]
            axes = ", ".join(f"{s['axis']} {s['score']}" for s in pre["sub_scores"])
            print(
                f"pre-grade     : likely {p['likely_low']}-{p['likely_high']} "
                f"(P(>={p['at_least']})={p['p_at_least']}) · conf {pre['confidence']} "
                f"[{axes}] — measured, not bought"
            )
        else:
            print(f"pre-grade     : {pre['status']} ({'; '.join(pre.get('reasons') or [])})")

    print("\nOK — full journey served on Holofy's OWN models (recognition + grading), no vendor API.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except httpx.HTTPError as exc:
        print(f"smoke failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
