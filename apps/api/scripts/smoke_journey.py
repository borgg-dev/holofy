"""End-to-end dev smoke: drives the whole Holofy API over HTTP, mock-first, no keys.

Run against a live server (see scripts/dev_smoke.sh). It mints a dev token and walks a real
user journey — scan (both outcomes), collection, portfolio, pre-grade, authenticity, consent —
printing each step so a human can see the product actually working end to end.
"""

from __future__ import annotations

import os
import sys
from io import BytesIO

import httpx
from PIL import Image, ImageDraw

from app.auth.dev_token import mint_dev_token
from app.config import INSECURE_DEV_SECRET

BASE_URL = os.environ.get("HOLOFY_SMOKE_BASE_URL", "http://127.0.0.1:8099")


def _eur(value: object) -> str:
    return f"€{value}" if value is not None else "—"


def _centered_card_png() -> bytes:
    """A real PNG of a centred bordered card — the stand-in for a camera still.

    Light card on a dark surface with an evenly-inset inner panel, so the in-house centering
    measurement has real pixels to read and returns a confident estimate, not a retake.
    """
    image = Image.new("L", (500, 700), color=30)
    draw = ImageDraw.Draw(image)
    draw.rectangle((24, 24, 476, 676), fill=235)
    draw.rectangle((64, 64, 436, 636), fill=90)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def main() -> int:
    token = mint_dev_token("demo-collector", secret=INSECURE_DEV_SECRET)
    auth = {"Authorization": f"Bearer {token}"}

    with httpx.Client(base_url=BASE_URL, headers=auth, timeout=10.0) as client:
        health = client.get("/health").json()
        print(f"health        : {health['status']} · region {health.get('data_region')}")

        unauth = httpx.get(f"{BASE_URL}/portfolio")
        print(f"authz guard   : no token -> {unauth.status_code} (expected 401)")

        resolved = client.post("/scan", json={"bundle_id": "mock-high-confidence"}).json()
        card = resolved["card"]
        print(
            f"scan (high)   : {resolved['outcome']} -> {card['identity']['name']} "
            f"({card['identity']['set_name']} {card['identity']['collector_number']}) "
            f"@ {_eur((card['price'] or {}).get('value'))}"
        )

        low = client.post("/scan", json={"bundle_id": "mock-low-confidence"}).json()
        a, b = low["choices"]
        print(
            f"scan (low)    : {low['outcome']} -> confirm "
            f"{a['identity']['set_name']} {_eur((a['price'] or {}).get('value'))} vs "
            f"{b['identity']['set_name']} {_eur((b['price'] or {}).get('value'))} "
            f"· delta {_eur(low['price_delta'])}"
        )

        batch = client.post(
            "/scan/batch",
            json={
                "items": [
                    {"bundle_id": "mock-high-confidence"},
                    {"bundle_id": "mock-high-confidence"},
                    {"bundle_id": "mock-high-confidence-2"},
                    {"bundle_id": "mock-unrecognized"},
                ]
            },
        ).json()
        q = batch["quota"]
        outcomes = ", ".join(
            f"{i['outcome']}×{i['count']}" for i in batch["items"]
        )
        print(
            f"scan (stack)  : {len(batch['items'])} card(s) [{outcomes}] · "
            f"charged {q['charged']}/{q['limit']} · {q['remaining']} left "
            f"(4 captures charged; 2 of one card deduped to one banked result)"
        )

        add = client.post("/collection", json={"canonical_id": "origins-8"}).json()
        print(f"collection add: {add['card']['name']} @ {_eur(add['unit_value_eur'])}")

        portfolio = client.get("/portfolio").json()
        print(
            f"portfolio     : {portfolio['item_count']} item(s) · "
            f"total {_eur(portfolio['total_value_eur'])}"
        )

        upload = client.post(
            "/captures",
            files=[("files", ("front.png", _centered_card_png(), "image/png"))],
        ).json()
        capture_ref = upload["ref"]
        print(
            f"upload        : stored {upload['image_count']} still(s) -> "
            f"ref {capture_ref[:8]}… (real bytes in object storage)"
        )

        pre = client.post(
            "/pregrade", json={"capture_ref": capture_ref, "card_id": "origins-8"}
        ).json()
        if pre["status"] == "estimated":
            p = pre["probability"]
            print(
                f"pre-grade     : likely {p['likely_low']}-{p['likely_high']} "
                f"(P(>={p['at_least']})={p['p_at_least']}) · conf {pre['confidence']}"
            )
        else:
            print(f"pre-grade     : {pre['status']}")

        auth_res = client.post(
            "/authenticity", json={"capture_ref": capture_ref, "card_id": "origins-8"}
        ).json()
        if auth_res["status"] == "assessed":
            a = auth_res["assessment"]
            print(
                f"authenticity  : {a['risk_band']} · evidence conf {a['confidence']} · "
                f"recommend_authentication={a['recommend_authentication']} (risk flag, no verdict)"
            )
        else:
            print(f"authenticity  : {auth_res['status']}")

        granted = client.put("/consent/training", json={"granted": True}).json()
        state = client.get("/consent/training").json()
        print(
            f"consent       : set granted={granted['granted']} · reads back "
            f"granted={state['granted']} (account-level)"
        )

    print("\nOK — full journey served end to end against the live API, mock-first, no keys.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except httpx.HTTPError as exc:
        print(f"smoke failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
