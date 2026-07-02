"""Production lifecycle + the Phase 8 hallmark gate:

  "a hallmark-required item can't ship without a hallmark record."

18k gold rings (≈5.9 g) are far above the 1 g gold threshold → required.
"""

from sqlalchemy import select

from app.db import get_session_factory
from app.models import ProductTemplate

SELECTIONS = {
    "metal": "gold_750_yellow",
    "stone_type": "lab_diamond",
    "stone_shape": "oval",
    "carat": "0.50",
    "certificate": "gia",
}


async def _paid_order_job(client) -> tuple[str, str]:
    """Create an order and pay the deposit → production job queued."""
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
    order = (
        await client.post(
            "/api/v1/orders",
            json={"quote_id": quote["id"], "customer": {"email": "fab@example.com"}},
        )
    ).json()
    intent = (
        await client.post(
            "/api/v1/payments/intent",
            json={"order_id": order["id"], "kind": "deposit_production"},
        )
    ).json()
    await client.post(f"/api/v1/payments/{intent['payment_id']}/mock-complete")

    jobs = (await client.get("/api/v1/production/jobs?status=queued")).json()
    job = next(j for j in jobs if j["order_item_id"] == order["items"][0]["id"])
    return order["id"], job["id"]


async def test_spec_sheet_carries_everything_the_factory_needs(client):
    _order_id, job_id = await _paid_order_job(client)
    sheet = (await client.get(f"/api/v1/production/jobs/{job_id}")).json()["spec_sheet"]
    assert sheet["configuration"]["metal"] == "gold_750_yellow"
    assert sheet["stone"]["carat"] == "0.50"
    assert sheet["weight"]["estimated_g"] is not None
    assert sheet["metal"] == "gold"
    assert sheet["hallmark_required"] is True  # 18k gold ring >> 1 g


async def test_hallmark_gate_blocks_then_allows_shipping(client):
    _order_id, job_id = await _paid_order_job(client)

    # Steps + QC progress normally.
    resp = await client.post(
        f"/api/v1/production/jobs/{job_id}/steps",
        json={"step": "casting", "status": "completed"},
    )
    assert resp.status_code == 201
    resp = await client.post(
        f"/api/v1/production/jobs/{job_id}/qc",
        json={"checklist": {"stones_secure": True}, "passed": True},
    )
    assert resp.json()["job_status"] == "qc_passed"

    # Shipping is BLOCKED before an applied hallmark.
    resp = await client.post(
        f"/api/v1/production/jobs/{job_id}/shipment",
        json={"carrier": "UPS", "tracking": "1Z999"},
    )
    assert resp.status_code == 409
    assert "hallmark required" in resp.json()["detail"]

    # A pending hallmark is not enough.
    resp = await client.post(
        f"/api/v1/production/jobs/{job_id}/hallmark",
        json={
            "fineness": 750,
            "responsibility_mark": "RM-PLACEHOLDER",
            "assay_office": "waarborg_holland",
            "status": "pending",
        },
    )
    assert resp.status_code == 201
    resp = await client.post(
        f"/api/v1/production/jobs/{job_id}/shipment",
        json={"carrier": "UPS", "tracking": "1Z999"},
    )
    assert resp.status_code == 409

    # Applied hallmark → shipping proceeds; order moves to shipped.
    await client.post(
        f"/api/v1/production/jobs/{job_id}/hallmark",
        json={
            "fineness": 750,
            "responsibility_mark": "RM-PLACEHOLDER",
            "assay_office": "waarborg_holland",
            "status": "applied",
        },
    )
    resp = await client.post(
        f"/api/v1/production/jobs/{job_id}/shipment",
        json={"carrier": "UPS", "tracking": "1Z999"},
    )
    assert resp.status_code == 201
    assert resp.json()["order_status"] == "shipped"


async def test_actual_weight_recorded_and_used(client):
    _order_id, job_id = await _paid_order_job(client)
    resp = await client.post(
        f"/api/v1/production/jobs/{job_id}/actual-weight", json={"grams": "6.120"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["actual_weight_g"] == "6.120"
    assert body["estimated_g"] is not None

    sheet = (await client.get(f"/api/v1/production/jobs/{job_id}")).json()["spec_sheet"]
    assert sheet["actual_weight_g"] == "6.120"


async def test_unknown_step_rejected(client):
    _order_id, job_id = await _paid_order_job(client)
    resp = await client.post(
        f"/api/v1/production/jobs/{job_id}/steps", json={"step": "teleport"}
    )
    assert resp.status_code == 422
