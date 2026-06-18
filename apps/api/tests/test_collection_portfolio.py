"""Collection and portfolio API coverage — the user-scoped half of the scan→portfolio slice.

A scanned card is addable to the collection, the collection lists with current € valuations,
the portfolio total reflects the added cards, a snapshot pins that total into the history,
and one collector can never see another's holdings. Runs on mock providers against the
in-memory database.
"""

from __future__ import annotations

from decimal import Decimal

from tests.conftest import auth_header


def _scan_and_add(client, headers, bundle="mock-high-confidence", **add):  # noqa: ANN001
    """Resolve a card via a scan (which lands it in the catalog) then add it to collection."""
    scan = client.post("/scan", json={"bundle_id": bundle}, headers=headers)
    assert scan.status_code == 200
    canonical_id = scan.json()["card"]["identity"]["canonical_id"]
    payload = {"canonical_id": canonical_id, **add}
    return client.post("/collection", json=payload, headers=headers)


def test_add_scanned_card_to_collection_returns_valuation(client) -> None:  # noqa: ANN001
    headers = auth_header()
    response = _scan_and_add(client, headers, quantity=2, condition="near_mint")

    assert response.status_code == 201
    body = response.json()
    assert body["card"]["canonical_id"] == "origins-8"
    assert body["quantity"] == 2
    # origins-8 mock trend is 289.00; the line value is unit × quantity.
    assert Decimal(body["unit_value_eur"]) == Decimal("289.00")
    assert Decimal(body["line_value_eur"]) == Decimal("578.00")


def test_adding_an_unknown_card_is_rejected(client) -> None:  # noqa: ANN001
    response = client.post(
        "/collection",
        json={"canonical_id": "never-scanned-1"},
        headers=auth_header(),
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "card_not_found"


def test_collection_lists_with_total_value(client) -> None:  # noqa: ANN001
    headers = auth_header("lister")
    _scan_and_add(client, headers, quantity=2)  # origins-8 @ 289.00 → 578.00

    response = client.get("/collection", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert body["currency"] == "EUR"
    assert Decimal(body["total_value_eur"]) == Decimal("578.00")


def test_portfolio_total_reflects_added_cards(client) -> None:  # noqa: ANN001
    headers = auth_header("investor")

    empty = client.get("/portfolio", headers=headers)
    assert Decimal(empty.json()["total_value_eur"]) == Decimal("0.00")

    _scan_and_add(
        client, headers, quantity=2, acquired_price_eur="120.00"
    )  # value 578.00, cost basis 240.00

    total = client.get("/portfolio", headers=headers).json()
    assert Decimal(total["total_value_eur"]) == Decimal("578.00")
    assert Decimal(total["total_cost_basis_eur"]) == Decimal("240.00")
    assert total["item_count"] == 2


def test_portfolio_snapshot_writes_and_reads_back_as_series(client) -> None:  # noqa: ANN001
    headers = auth_header("charter")
    _scan_and_add(client, headers, quantity=1)

    snapshot = client.post("/portfolio/snapshots", headers=headers)
    assert snapshot.status_code == 201
    assert Decimal(snapshot.json()["total_value_eur"]) == Decimal("289.00")

    history = client.get("/portfolio/snapshots", headers=headers)
    assert history.status_code == 200
    snapshots = history.json()["snapshots"]
    assert len(snapshots) == 1
    assert Decimal(snapshots[0]["total_value_eur"]) == Decimal("289.00")


def test_collection_is_scoped_to_the_authenticated_user(client) -> None:  # noqa: ANN001
    owner = auth_header("owner")
    _scan_and_add(client, owner, quantity=1)

    # A different user sees an empty collection and a zero portfolio — no cross-tenant leak.
    other = auth_header("intruder")
    assert client.get("/collection", headers=other).json()["items"] == []
    assert Decimal(
        client.get("/portfolio", headers=other).json()["total_value_eur"]
    ) == Decimal("0.00")


def test_collection_requires_authentication(client) -> None:  # noqa: ANN001
    assert client.get("/collection").status_code == 401
    assert client.get("/portfolio").status_code == 401
