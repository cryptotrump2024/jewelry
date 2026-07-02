"""Admin pricing-config API: read the full config, edit values, refresh

metals, import diamond prices — and the edit flows straight into the live
price preview (rules over hardcoding, end to end). Plus the auth guard.
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


async def test_config_returns_all_sections(client):
    resp = await client.get("/admin/pricing/config")
    assert resp.status_code == 200
    body = resp.json()
    assert {r["operation"] for r in body["labor"]} == {"setting", "casting", "polishing"}
    assert len(body["margins"]) == 1 and body["margins"][0]["value"] == "0.6000"
    assert {r["kind"] for r in body["buffers"]} == {"shipping", "payment_fee"}
    assert body["vat_rules"][0]["market"] == "NL"
    assert any(s["provider"] == "manual" for s in body["metal_sources"])
    assert len(body["latest_metal_prices"]) > 0


async def test_labor_edit_flows_into_price_preview(client):
    config = (await client.get("/admin/pricing/config")).json()
    setting = next(r for r in config["labor"] if r["operation"] == "setting")
    original = setting["amount_minor"]
    template_id = await _template_id()

    try:
        resp = await client.put(
            f"/admin/pricing/labor/{setting['id']}", json={"amount_minor": original + 1000}
        )
        assert resp.status_code == 200

        preview = (
            await client.post(
                f"/admin/templates/{template_id}/price-preview",
                json={"selections": SELECTIONS},
            )
        ).json()
        assert preview["price"]["itemized"]["setting_labor"] == original + 1000
    finally:
        await client.put(
            f"/admin/pricing/labor/{setting['id']}", json={"amount_minor": original}
        )


async def test_margin_edit_changes_total(client):
    config = (await client.get("/admin/pricing/config")).json()
    margin = config["margins"][0]
    template_id = await _template_id()

    before = (
        await client.post(
            f"/admin/templates/{template_id}/price-preview", json={"selections": SELECTIONS}
        )
    ).json()["price"]["total_minor"]

    try:
        resp = await client.put(
            f"/admin/pricing/margins/{margin['id']}", json={"value": "0.75"}
        )
        assert resp.status_code == 200
        after = (
            await client.post(
                f"/admin/templates/{template_id}/price-preview", json={"selections": SELECTIONS}
            )
        ).json()["price"]["total_minor"]
        assert after > before
    finally:
        await client.put(
            f"/admin/pricing/margins/{margin['id']}", json={"value": margin["value"]}
        )


async def test_manual_metal_price_update_refreshes_snapshots(client):
    resp = await client.put(
        "/admin/pricing/manual-metal-prices",
        json={"prices": [{"metal": "gold", "karat": 18, "price_per_gram": "90.00"}]},
    )
    assert resp.status_code == 200
    assert resp.json()["snapshots_written"] == 1

    config = (await client.get("/admin/pricing/config")).json()
    latest_18k = next(
        p
        for p in config["latest_metal_prices"]
        if p["metal"] == "gold" and p["karat"] == 18
    )
    assert latest_18k["price_per_gram"] == "90.0000"

    # Restore the full seeded price list for other tests.
    from app.seeds.pricing import MANUAL_METAL_PRICES

    resp = await client.put(
        "/admin/pricing/manual-metal-prices", json={"prices": MANUAL_METAL_PRICES}
    )
    assert resp.json()["snapshots_written"] == len(MANUAL_METAL_PRICES)


async def test_diamond_import_endpoint_dry_run_then_commit(client):
    csv_text = (
        "stone_type,shape,carat_min,carat_max,color,clarity,price_per_carat,currency\n"
        "lab_diamond,round,3.00,3.99,G,SI1,3000,EUR\n"
    )
    resp = await client.post(
        "/admin/pricing/imports/diamond-prices", json={"csv_text": csv_text, "dry_run": True}
    )
    body = resp.json()
    assert body["dry_run"] is True and body["stats"]["ok"] == 1

    resp = await client.post(
        "/admin/pricing/imports/diamond-prices", json={"csv_text": csv_text, "dry_run": False}
    )
    assert resp.json()["stats"]["created"] == 1


async def test_admin_auth_guard(client, monkeypatch):
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "admin_api_token", "secret-token")

    resp = await client.get("/admin/pricing/config")
    assert resp.status_code == 401

    resp = await client.get(
        "/admin/pricing/config", headers={"authorization": "Bearer wrong"}
    )
    assert resp.status_code == 401

    resp = await client.get(
        "/admin/pricing/config", headers={"authorization": "Bearer secret-token"}
    )
    assert resp.status_code == 200

    # Public endpoints unaffected.
    resp = await client.get("/health")
    assert resp.status_code == 200
