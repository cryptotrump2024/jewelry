"""Bespoke workflow (docs/spec/10, FRD criterion 4): request → design deposit

→ revisions → quote → approval → order, with the design deposit credited so
the balance is total − production deposit − design deposit.
"""


async def _request(client) -> str:
    resp = await client.post(
        "/api/v1/bespoke/requests",
        json={
            "source": "upload",
            "brief": {"idea": "vintage halo with heirloom stone", "budget_minor": 500000},
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "new"
    # Rough range from the stated budget (±20%).
    assert body["price_range"] == {
        "min_minor": 400000,
        "max_minor": 600000,
        "currency": "EUR",
    }
    return body["id"]


async def test_full_bespoke_journey(client):
    rid = await _request(client)

    # Revisions before the design deposit are refused.
    resp = await client.post(f"/api/v1/bespoke/requests/{rid}/revisions", json={"notes": "v1"})
    assert resp.status_code == 409

    # Design deposit: €250 (decision #4), then the request enters design.
    resp = await client.post(f"/api/v1/bespoke/requests/{rid}/design-deposit")
    assert resp.status_code == 201
    intent = resp.json()
    assert intent["amount"]["amount_minor"] == 25000
    resp = await client.post(f"/api/v1/payments/{intent['payment_id']}/mock-complete")
    assert resp.json() == {"payment_status": "paid", "order_status": None}

    detail = (await client.get(f"/api/v1/bespoke/requests/{rid}")).json()
    assert detail["status"] == "in_design"

    # CAD/render revision rounds.
    resp = await client.post(
        f"/api/v1/bespoke/requests/{rid}/revisions", json={"notes": "first CAD"}
    )
    assert resp.json()["round_no"] == 1
    resp = await client.post(
        f"/api/v1/bespoke/requests/{rid}/revisions", json={"notes": "thinner prongs"}
    )
    assert resp.json()["round_no"] == 2

    # Approval before a quote is refused.
    resp = await client.post(
        f"/api/v1/bespoke/requests/{rid}/approve", json={"approved_by": "customer"}
    )
    assert resp.status_code == 409

    # Admin quotes the design.
    itemized = {"materials": 200000, "stones": 180000, "labor": 70000, "vat": 94500}
    resp = await client.post(
        f"/api/v1/bespoke/requests/{rid}/quote",
        json={"itemized": itemized, "total_minor": 544500},
    )
    assert resp.status_code == 201
    assert resp.json()["request_status"] == "quoted"

    # Customer approves → bespoke order with locked quote-based snapshot.
    resp = await client.post(
        f"/api/v1/bespoke/requests/{rid}/approve", json={"approved_by": "customer"}
    )
    assert resp.status_code == 200
    body = resp.json()
    order_id = body["order_id"]
    assert body["order_status"] == "awaiting_deposit"
    assert body["totals"]["total_minor"] == 544500

    order = (await client.get(f"/api/v1/orders/{order_id}")).json()
    assert order["items"][0]["non_returnable"] is True  # bespoke = always exempt

    # Production deposit (50%).
    resp = await client.post(
        "/api/v1/payments/intent",
        json={"order_id": order_id, "kind": "deposit_production"},
    )
    dep = resp.json()
    assert dep["amount"]["amount_minor"] == 272250
    await client.post(f"/api/v1/payments/{dep['payment_id']}/mock-complete")

    # Balance = total − production deposit − credited design deposit.
    resp = await client.post(
        "/api/v1/payments/intent", json={"order_id": order_id, "kind": "balance"}
    )
    bal = resp.json()
    assert bal["amount"]["amount_minor"] == 544500 - 272250 - 25000
    await client.post(f"/api/v1/payments/{bal['payment_id']}/mock-complete")

    # Fully paid: nothing left.
    resp = await client.post(
        "/api/v1/payments/intent", json={"order_id": order_id, "kind": "balance"}
    )
    assert resp.status_code == 422
    assert "nothing left" in resp.json()["detail"]

    order = (await client.get(f"/api/v1/orders/{order_id}")).json()
    assert order["status"] == "paid"


async def test_quote_must_match_itemized_sum(client):
    rid = await _request(client)
    intent = (await client.post(f"/api/v1/bespoke/requests/{rid}/design-deposit")).json()
    await client.post(f"/api/v1/payments/{intent['payment_id']}/mock-complete")

    resp = await client.post(
        f"/api/v1/bespoke/requests/{rid}/quote",
        json={"itemized": {"materials": 100}, "total_minor": 999},
    )
    assert resp.status_code == 409
    assert "equal the itemized sum" in resp.json()["detail"]
