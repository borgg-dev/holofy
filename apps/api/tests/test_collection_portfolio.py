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
    body = scan.json()
    # The scan also carries the game on the identity (Pokémon by default).
    assert body["card"]["identity"]["game"]["id"] == "pokemon"
    canonical_id = body["card"]["identity"]["canonical_id"]
    payload = {"canonical_id": canonical_id, **add}
    return client.post("/collection", json=payload, headers=headers)


def test_add_scanned_card_to_collection_returns_valuation(client) -> None:  # noqa: ANN001
    headers = auth_header()
    response = _scan_and_add(client, headers, quantity=2, condition="near_mint")

    assert response.status_code == 201
    body = response.json()
    assert body["identity"]["canonical_id"] == "origins-8"
    # The game travels on the identity (Pokémon by default) — what the Vault groups on.
    assert body["identity"]["game"] == {"id": "pokemon", "name": "Pokémon"}
    assert body["quantity"] == 2
    # origins-8 mock trend is 289.00; the line value is unit × quantity.
    assert Decimal(body["unit_value_eur"]) == Decimal("289.00")
    assert Decimal(body["line_value_eur"]) == Decimal("578.00")
    # The full quote rides along so the detail screen can show provenance/freshness.
    assert Decimal(body["price"]["value"]) == Decimal("289.00")


def test_remove_card_from_collection(client) -> None:  # noqa: ANN001
    headers = auth_header("remover")
    added = _scan_and_add(client, headers, quantity=1)
    item_id = added.json()["id"]

    # The holding is present...
    assert len(client.get("/collection", headers=headers).json()) == 1
    # ...removing it returns 204 and empties the Vault.
    deleted = client.delete(f"/collection/{item_id}", headers=headers)
    assert deleted.status_code == 204
    assert client.get("/collection", headers=headers).json() == []


def test_remove_missing_item_is_404(client) -> None:  # noqa: ANN001
    import uuid

    response = client.delete(f"/collection/{uuid.uuid4()}", headers=auth_header())
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "collection_item_not_found"


def test_cannot_remove_another_users_card(client) -> None:  # noqa: ANN001
    owner = auth_header("owner-del")
    item_id = _scan_and_add(client, owner, quantity=1).json()["id"]
    # A different user must not be able to delete it — owner-scoped, so it reads as a 404.
    other = client.delete(f"/collection/{item_id}", headers=auth_header("intruder-del"))
    assert other.status_code == 404
    # And the owner's holding is untouched.
    assert len(client.get("/collection", headers=owner).json()) == 1


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
    items = response.json()  # a bare array of valued holdings
    assert len(items) == 1
    assert Decimal(items[0]["line_value_eur"]) == Decimal("578.00")


def test_portfolio_total_reflects_added_cards(client) -> None:  # noqa: ANN001
    headers = auth_header("investor")

    empty = client.get("/portfolio", headers=headers).json()
    assert Decimal(empty["latest"]["total_value_eur"]) == Decimal("0.00")
    assert empty["previous"] is None  # fresh account has no prior snapshot

    _scan_and_add(
        client, headers, quantity=2, acquired_price_eur="120.00"
    )  # value 578.00, cost basis 240.00

    latest = client.get("/portfolio", headers=headers).json()["latest"]
    assert Decimal(latest["total_value_eur"]) == Decimal("578.00")
    assert Decimal(latest["total_cost_basis_eur"]) == Decimal("240.00")
    assert latest["item_count"] == 2


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


def test_snapshot_all_due_covers_every_holder_and_is_idempotent(client) -> None:  # noqa: ANN001
    # Two distinct accounts each hold a card; the daily job must snapshot both, once.
    a, b = auth_header("holder-a"), auth_header("holder-b")
    assert _scan_and_add(client, a).status_code == 201
    assert _scan_and_add(client, b).status_code == 201

    from app.db.repositories import CardRepository, CollectionRepository, PortfolioRepository
    from app.services.collection import CollectionService
    from app.services.portfolio import PortfolioService

    async def run_due() -> int:
        factory = client.app.state.session_factory
        async with factory() as session:
            service = PortfolioService(
                collection=CollectionService(
                    cards=CardRepository(session),
                    collection=CollectionRepository(session),
                    pricing=client.app.state.pricing_provider,
                ),
                portfolio=PortfolioRepository(session),
            )
            written = await service.snapshot_all_due()
            await session.commit()
            return written

    assert client.portal.call(run_due) == 2  # both holders pinned
    assert client.portal.call(run_due) == 0  # within the interval → no duplicate day

    # The series now carries one honest point for a holder.
    history = client.get("/portfolio/snapshots", headers=a)
    assert len(history.json()["snapshots"]) == 1


def test_collection_is_scoped_to_the_authenticated_user(client) -> None:  # noqa: ANN001
    owner = auth_header("owner")
    _scan_and_add(client, owner, quantity=1)

    # A different user sees an empty collection and a zero portfolio — no cross-tenant leak.
    other = auth_header("intruder")
    assert client.get("/collection", headers=other).json() == []
    assert Decimal(
        client.get("/portfolio", headers=other).json()["latest"]["total_value_eur"]
    ) == Decimal("0.00")


def test_collection_requires_authentication(client) -> None:  # noqa: ANN001
    assert client.get("/collection").status_code == 401
    assert client.get("/portfolio").status_code == 401
