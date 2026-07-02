"""EU withdrawal function (docs/spec/12 §3a, Phase 8 exit): two-step flow

with durable-medium acknowledgement; personalised items are exempt but the
function must exist for eligible ones.
"""

import uuid

from sqlalchemy import select, update

from app.db import get_session_factory
from app.models import OrderItem, ProductTemplate

SELECTIONS = {
    "metal": "gold_750_yellow",
    "stone_type": "lab_diamond",
    "stone_shape": "oval",
    "carat": "0.50",
    "certificate": "gia",
}


async def _make_order(client) -> dict:
    async with get_session_factory()() as session:
        template = (
            await session.execute(
                select(ProductTemplate).where(ProductTemplate.code == "oval-solitaire")
            )
        ).scalar_one()
        template_id = str(template.id)
    quote = (
        await client.post(
            "/api/v1/quotes", json={"template_id": template_id, "selections": SELECTIONS}
        )
    ).json()
    resp = await client.post(
        "/api/v1/orders",
        json={"quote_id": quote["id"], "customer": {"email": "wd@example.com"}},
    )
    assert resp.status_code == 201
    return resp.json()


async def test_two_step_withdrawal_with_acknowledgement(client):
    order = await _make_order(client)

    resp = await client.get(f"/api/v1/orders/{order['id']}/withdrawal-eligibility")
    eligibility = resp.json()
    assert eligibility["per_item"][0]["status"] == "eligible"

    # Step 1: initiate.
    resp = await client.post(
        "/api/v1/withdrawals",
        json={"order_id": order["id"], "name": "W. Draw", "contact": "wd@example.com"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "initiated"
    wid = body["withdrawal_request_id"]

    # Step 2: confirm → acknowledged on a durable medium with date + time.
    resp = await client.post(f"/api/v1/withdrawals/{wid}/confirm")
    body = resp.json()
    assert body["status"] == "acknowledged"
    assert body["confirmed_at"] and body["acknowledged_at"]
    assert body["ack_medium"] == "email"

    # Idempotent confirm.
    resp = await client.post(f"/api/v1/withdrawals/{wid}/confirm")
    assert resp.json()["status"] == "acknowledged"

    resp = await client.get(f"/api/v1/withdrawals/{wid}")
    assert resp.json()["status"] == "acknowledged"


async def test_personalised_items_are_exempt(client):
    order = await _make_order(client)
    async with get_session_factory()() as session:
        await session.execute(
            update(OrderItem)
            .where(OrderItem.order_id == uuid.UUID(order["id"]))
            .values(non_returnable=True)
        )
        await session.commit()

    resp = await client.get(f"/api/v1/orders/{order['id']}/withdrawal-eligibility")
    assert resp.json()["per_item"][0]["status"] == "exempt_personalised"

    resp = await client.post(
        "/api/v1/withdrawals",
        json={"order_id": order["id"], "name": "W. Draw", "contact": "wd@example.com"},
    )
    assert resp.status_code == 409
    assert "exempt" in resp.json()["detail"]
