"""Phase 5 "live breakdown": the seeded demo template prices end-to-end from

pure data — rules validate, weight from CAD volumes × seeded density, metal
from the manual-source snapshot, stone from the seeded price table with the
magic-size band, labor/margin/buffers/VAT from pricing config.
"""

from sqlalchemy import select

from app.db import get_session_factory
from app.models import ProductTemplate


async def _template_id() -> str:
    async with get_session_factory()() as session:
        template = (
            await session.execute(
                select(ProductTemplate).where(ProductTemplate.code == "oval-solitaire")
            )
        ).scalar_one()
        return str(template.id)


BASE_SELECTIONS = {
    "metal": "gold_750_yellow",
    "stone_type": "lab_diamond",
    "stone_shape": "oval",
    "carat": "1.00",
    "certificate": "igi",
    "ring_size": "54",
}


async def test_demo_template_prices_end_to_end(client):
    tid = await _template_id()
    resp = await client.post(
        f"/admin/templates/{tid}/price-preview", json={"selections": BASE_SELECTIONS}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["validation"]["status"] == "purchasable"
    price = body["price"]
    assert price["status"] == "purchasable"
    assert price["total_minor"] > 0

    itemized = price["itemized"]
    # Weight: (290+62+18)/1000 cm³ × 15.58 × 1.02 = 5.880 g; × €84 × 1.05.
    assert itemized["metal_cost"] == 51862
    # Stone: 1.00 ct in the 1.00–1.49 band (€1500/ct) × magic 1.20.
    assert itemized["center_stone_cost"] == 180000
    assert itemized["setting_labor"] == 4500
    assert itemized["casting_labor"] == 6000
    assert itemized["polishing_labor"] == 2500
    assert itemized["shipping_buffer"] == 2500
    assert "margin" in itemized and "vat" in itemized


async def test_carat_below_magic_size_no_multiplier(client):
    tid = await _template_id()
    resp = await client.post(
        f"/admin/templates/{tid}/price-preview",
        json={"selections": BASE_SELECTIONS | {"carat": "0.70"}},
    )
    body = resp.json()
    # 0.70 ct in the 0.70–0.99 band (€1100/ct) × no band crossed = €770.
    assert body["price"]["itemized"]["center_stone_cost"] == 77000


async def test_natural_diamond_prices_from_different_table(client):
    tid = await _template_id()
    resp = await client.post(
        f"/admin/templates/{tid}/price-preview",
        json={"selections": BASE_SELECTIONS | {"stone_type": "natural_diamond"}},
    )
    body = resp.json()
    # natural = lab × 3.3: 1500 × 3.3 = 4950/ct × 1.00 × 1.20 = €5940.
    assert body["price"]["itemized"]["center_stone_cost"] == 594000


async def test_missing_certificate_above_threshold_is_invalid_no_price(client):
    tid = await _template_id()
    selections = dict(BASE_SELECTIONS)
    del selections["certificate"]
    resp = await client.post(
        f"/admin/templates/{tid}/price-preview", json={"selections": selections}
    )
    body = resp.json()
    assert body["validation"]["status"] == "invalid"
    assert body["price"] is None  # invalid configs are never priced
    assert "certificate" in body["validation"]["required_groups"]


async def test_out_of_table_carat_is_quote_only(client):
    tid = await _template_id()
    resp = await client.post(
        f"/admin/templates/{tid}/price-preview",
        json={"selections": BASE_SELECTIONS | {"carat": "5.00"}},
    )
    body = resp.json()
    assert body["validation"]["status"] == "purchasable"  # rules allow it
    price = body["price"]
    assert price["status"] == "quote_only"  # no table row for 5 ct
    assert price["total_minor"] is None
    assert any(r["code"] == "stone_price_unavailable" for r in price["reasons"])


async def test_unpriceable_market_vat_missing_is_quote_only(client):
    tid = await _template_id()
    resp = await client.post(
        f"/admin/templates/{tid}/price-preview",
        json={"selections": BASE_SELECTIONS, "market": "JP"},
    )
    body = resp.json()
    assert body["price"]["status"] == "quote_only"
    assert any(r["code"] == "vat_rule_missing" for r in body["price"]["reasons"])
