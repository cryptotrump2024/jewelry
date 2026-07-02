"""Quote → order → deposit flow over the public API.

Covers the Phase 7 exit's checkout leg and Phase 8 groundwork: authoritative
requote at quote time, immutable snapshot locked to the order (spec test:
gold price changes later must NOT move an existing order's total), 50%
deposit default, mock-PSP completion advancing order + production job.
"""

from sqlalchemy import select

from app.db import get_session_factory
from app.models import ProductTemplate

SELECTIONS = {
    "metal": "gold_750_yellow",
    "stone_type": "lab_diamond",
    "stone_shape": "oval",
    "carat": "1.00",
    "certificate": "igi",
}


async def _template_id() -> str:
    async with get_session_factory()() as session:
        template = (
            await session.execute(
                select(ProductTemplate).where(ProductTemplate.code == "oval-solitaire")
            )
        ).scalar_one()
        return str(template.id)


async def _quote(client, selections=None) -> dict:
    resp = await client.post(
        "/api/v1/quotes",
        json={"template_id": await _template_id(), "selections": selections or SELECTIONS},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_full_checkout_flow(client):
    quote = await _quote(client)
    assert quote["status"] == "open"
    total = quote["total"]["amount_minor"]
    assert total > 0

    # Quote matches the advisory price endpoint (authoritative recompute).
    advisory = (
        await client.post(
            "/api/v1/config/price",
            json={"template_id": await _template_id(), "selections": SELECTIONS},
        )
    ).json()
    assert advisory["total"]["amount_minor"] == total

    resp = await client.post(
        "/api/v1/orders",
        json={"quote_id": quote["id"], "customer": {"email": "buyer@example.com", "name": "B"}},
    )
    assert resp.status_code == 201, resp.text
    order = resp.json()
    assert order["status"] == "awaiting_deposit"
    assert order["totals"]["total_minor"] == total
    assert order["totals"]["deposit_minor"] == (total + 1) // 2  # 50%, ceil
    assert len(order["items"]) == 1
    assert order["items"][0]["price_snapshot_id"]

    # Deposit intent via the (mock) PSP adapter.
    resp = await client.post(
        "/api/v1/payments/intent",
        json={"order_id": order["id"], "kind": "deposit_production"},
    )
    assert resp.status_code == 201
    intent = resp.json()
    assert intent["amount"]["amount_minor"] == order["totals"]["deposit_minor"]

    # PSP "webhook" completes → order and production job advance.
    resp = await client.post(f"/api/v1/payments/{intent['payment_id']}/mock-complete")
    assert resp.json() == {"payment_status": "paid", "order_status": "in_production"}

    # Idempotent completion.
    resp = await client.post(f"/api/v1/payments/{intent['payment_id']}/mock-complete")
    assert resp.json()["payment_status"] == "paid"

    order_after = (await client.get(f"/api/v1/orders/{order['id']}")).json()
    assert order_after["status"] == "in_production"
    assert order_after["payments"][0]["status"] == "paid"

    # Quote is consumed.
    resp = await client.post(
        "/api/v1/orders",
        json={"quote_id": quote["id"], "customer": {"email": "buyer@example.com"}},
    )
    assert resp.status_code == 409


async def test_invalid_config_cannot_be_quoted(client):
    resp = await client.post(
        "/api/v1/quotes",
        json={
            "template_id": await _template_id(),
            "selections": SELECTIONS | {"carat": "1.50", "certificate": None},
        },
    )
    assert resp.status_code == 409
    assert "invalid" in resp.json()["detail"]


async def test_unpriceable_config_cannot_be_quoted_exactly(client):
    resp = await client.post(
        "/api/v1/quotes",
        json={
            "template_id": await _template_id(),
            "selections": SELECTIONS | {"carat": "5.00"},  # outside price tables
        },
    )
    assert resp.status_code == 409
    assert "not firmly priceable" in resp.json()["detail"]


async def test_order_total_immune_to_later_price_changes(client):
    """The core snapshot guarantee at the API level: change the gold price

    after an order exists — the order's stored total must not move, while a
    fresh quote prices differently.
    """
    quote = await _quote(client)
    resp = await client.post(
        "/api/v1/orders",
        json={"quote_id": quote["id"], "customer": {"email": "lock@example.com"}},
    )
    order = resp.json()
    locked_total = order["totals"]["total_minor"]

    # Gold jumps 20%.
    resp = await client.put(
        "/admin/pricing/manual-metal-prices",
        json={"prices": [{"metal": "gold", "karat": 18, "price_per_gram": "100.80"}]},
    )
    assert resp.status_code == 200

    try:
        order_after = (await client.get(f"/api/v1/orders/{order['id']}")).json()
        assert order_after["totals"]["total_minor"] == locked_total  # frozen

        fresh = await _quote(client)
        assert fresh["total"]["amount_minor"] != locked_total  # new price for new quotes
    finally:
        from app.seeds.pricing import MANUAL_METAL_PRICES

        await client.put(
            "/admin/pricing/manual-metal-prices", json={"prices": MANUAL_METAL_PRICES}
        )


async def test_order_requires_valid_email(client):
    quote = await _quote(client)
    resp = await client.post(
        "/api/v1/orders", json={"quote_id": quote["id"], "customer": {"email": "nope"}}
    )
    assert resp.status_code == 422
