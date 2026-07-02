"""Phase 6 exit (docs/spec/14): FRD MVP acceptance criteria 1–3 against the

headless API, < 300 ms p95.

Criterion 1 (admin builds template, no code) is proven by the admin-API
tests; here criteria 2–3: a visitor configures via the public API, invalid
combos are blocked with reasons, live prices show instantly with a breakdown,
metal/carat changes reprice from spot + carat bands, never NaN.
"""

import time

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


# --- Catalog reads ---


async def test_catalog_endpoints(client):
    resp = await client.get("/api/v1/categories")
    assert resp.status_code == 200
    assert any(c["slug"] == "engagement-ring" for c in resp.json())

    resp = await client.get("/api/v1/templates?category=engagement-ring")
    assert resp.status_code == 200
    codes = {t["code"] for t in resp.json()}
    assert "oval-solitaire" in codes

    tid = await _template_id()
    resp = await client.get(f"/api/v1/templates/{tid}")
    body = resp.json()
    assert body["code"] == "oval-solitaire"
    assert {c["kind"] for c in body["components"]} >= {"shank", "head", "center_stone"}
    metal_group = next(g for g in body["option_groups"] if g["key"] == "metal")
    assert metal_group["default_option_code"] == "gold_750_yellow"
    assert len(metal_group["options"]) == 10  # material_options only

    resp = await client.get(f"/api/v1/templates/{tid}/rules")
    assert resp.json()["version"] >= 1
    assert any(r["type"] == "requirement" for r in resp.json()["rules"])

    resp = await client.get("/api/v1/ring-sizes?standard=EU")
    sizes = resp.json()
    assert len(sizes) == 19 and sizes[0]["label"] == "44"


# --- Criterion 2: configure, block invalid with reasons, live price ---


async def test_visitor_flow_valid_config_prices_with_breakdown(client):
    tid = await _template_id()
    resp = await client.post(
        "/api/v1/config/price", json={"template_id": tid, "selections": SELECTIONS}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["validity"]["status"] == "purchasable"
    assert body["total"]["amount_minor"] > 0
    assert body["total"]["currency"] == "EUR"
    assert set(body["itemized"]) >= {"metal_cost", "center_stone_cost", "margin", "vat"}
    assert body["weight"]["source"] == "estimated"
    assert body["config_hash"]


async def test_invalid_combo_blocked_with_reasons(client):
    tid = await _template_id()
    resp = await client.post(
        "/api/v1/config/validate",
        json={
            "template_id": tid,
            "selections": SELECTIONS | {"carat": "1.50", "certificate": None},
        },
    )
    body = resp.json()
    assert body["status"] == "invalid"
    assert any("certificate" in r["message"].lower() for r in body["reasons"])
    assert "certificate" in body["required_groups"]

    # Price endpoint returns no price for it either — never a fake number.
    resp = await client.post(
        "/api/v1/config/price",
        json={
            "template_id": tid,
            "selections": SELECTIONS | {"carat": "1.50", "certificate": None},
        },
    )
    body = resp.json()
    assert body["validity"]["status"] == "invalid"
    assert "total" not in body and "estimated_range" not in body


# --- Criterion 3: changes reprice from spot + carat bands, never NaN ---


async def test_metal_and_carat_changes_reprice(client):
    tid = await _template_id()

    async def price(sel):
        resp = await client.post(
            "/api/v1/config/price", json={"template_id": tid, "selections": sel}
        )
        return resp.json()

    base = await price(SELECTIONS)
    metal_14k = await price(SELECTIONS | {"metal": "gold_585_yellow"})
    platinum = await price(SELECTIONS | {"metal": "platinum_950"})
    carat_070 = await price(SELECTIONS | {"carat": "0.70"})

    # Metal change: 14k cheaper than 18k (lower density × lower spot).
    assert metal_14k["itemized"]["metal_cost"] < base["itemized"]["metal_cost"]
    assert platinum["itemized"]["metal_cost"] != base["itemized"]["metal_cost"]

    # Carat band + magic size: 1.00 ct jumps non-linearly vs 0.70 ct.
    ratio = base["itemized"]["center_stone_cost"] / carat_070["itemized"]["center_stone_cost"]
    assert ratio > (1.00 / 0.70)  # more than linear

    # Never NaN: every number in every response is an int.
    for body in (base, metal_14k, platinum, carat_070):
        assert all(isinstance(v, int) for v in body["itemized"].values())
        assert isinstance(body["total"]["amount_minor"], int)


# --- Share round-trip (07 §9 case 6) ---


async def test_share_roundtrip_reproduces_selection_and_price(client):
    tid = await _template_id()
    resp = await client.post(
        "/api/v1/config/share", json={"template_id": tid, "selections": SELECTIONS}
    )
    assert resp.status_code == 200
    code = resp.json()["code"]

    resp = await client.get(f"/api/v1/config/{code}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["selections"] == SELECTIONS
    assert body["price"]["validity"]["status"] == "purchasable"

    direct = await client.post(
        "/api/v1/config/price", json={"template_id": tid, "selections": SELECTIONS}
    )
    assert body["price"]["total"] == direct.json()["total"]


async def test_bogus_share_code_404s(client):
    resp = await client.get("/api/v1/config/not-a-real-code")
    assert resp.status_code == 404


# --- Determinism + latency ---


async def test_identical_input_identical_output_and_hash(client):
    tid = await _template_id()
    payload = {"template_id": tid, "selections": SELECTIONS}
    first = (await client.post("/api/v1/config/price", json=payload)).json()
    second = (await client.post("/api/v1/config/price", json=payload)).json()
    assert first == second  # cacheable by config_hash


async def test_price_latency_p95_under_300ms(client):
    tid = await _template_id()
    # Vary carat so the Redis cache can't mask compute time for every call.
    carats = ["0.30", "0.50", "0.70", "1.00", "1.50", "2.00"]
    durations = []
    for i in range(30):
        sel = SELECTIONS | {"carat": carats[i % len(carats)]}
        start = time.perf_counter()
        resp = await client.post(
            "/api/v1/config/price", json={"template_id": tid, "selections": sel}
        )
        durations.append(time.perf_counter() - start)
        assert resp.status_code == 200
    durations.sort()
    p95 = durations[int(len(durations) * 0.95) - 1]
    assert p95 < 0.300, f"p95 {p95 * 1000:.1f} ms exceeds 300 ms"
