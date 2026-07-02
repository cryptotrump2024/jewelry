"""Admin API: template/rule CRUD and the simulator-gated publish flow.

End-to-end over HTTP: a template is built via the API alone (the Phase 5
backend contract the admin UI will drive), and a contradictory rule set is
refused at publish.
"""

from sqlalchemy import select

from app.db import get_session_factory
from app.models import Category, Tenant


async def _category_id() -> str:
    async with get_session_factory()() as session:
        tenant = (
            await session.execute(select(Tenant).where(Tenant.slug == "default"))
        ).scalar_one()
        category = (
            await session.execute(
                select(Category).where(
                    Category.tenant_id == tenant.id, Category.slug == "engagement-ring"
                )
            )
        ).scalar_one()
        return str(category.id)


async def _build_template(client, code: str) -> str:
    resp = await client.post(
        "/admin/templates",
        json={"category_id": await _category_id(), "code": code, "name": "Test Halo"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _make_group(client, key: str, options: list[str]) -> str:
    resp = await client.post("/admin/option-groups", json={"key": key, "name": key.title()})
    assert resp.status_code == 201, resp.text
    group_id = resp.json()["id"]
    for i, code in enumerate(options):
        resp = await client.post(
            f"/admin/option-groups/{group_id}/options",
            json={"code": code, "label": code, "sort": i},
        )
        assert resp.status_code == 201, resp.text
    return group_id


async def test_admin_builds_template_and_publishes_rules(client):
    template_id = await _build_template(client, "test-halo")

    metal_group = await _make_group(client, "test_metal", ["gold_750", "platinum_950"])
    carat_group = await _make_group(client, "test_carat", ["0.30", "0.50", "1.00"])
    cert_group = await _make_group(client, "test_certificate", ["gia", "igi"])

    for i, gid in enumerate([metal_group, carat_group, cert_group]):
        resp = await client.post(
            f"/admin/templates/{template_id}/option-groups",
            json={"option_group_id": gid, "step_order": i + 1},
        )
        assert resp.status_code == 201, resp.text

    resp = await client.post(f"/admin/templates/{template_id}/rule-sets")
    assert resp.status_code == 201
    rule_set_id = resp.json()["id"]
    assert resp.json()["version"] == 1

    resp = await client.post(
        f"/admin/rule-sets/{rule_set_id}/rules",
        json={
            "type": "requirement",
            "condition": {">": [{"var": "test_carat"}, 0.30]},
            "effect": {"require_option_group": "test_certificate"},
            "message": "Certificate required above 0.30 ct.",
        },
    )
    assert resp.status_code == 201

    # Preview first.
    resp = await client.get(f"/admin/rule-sets/{rule_set_id}/simulate")
    assert resp.status_code == 200
    report = resp.json()
    assert report["ok"] is True
    assert report["total_combinations"] == 12

    # Publish succeeds.
    resp = await client.post(f"/admin/rule-sets/{rule_set_id}/publish")
    assert resp.status_code == 200
    assert resp.json()["status"] == "published"

    # A published set is immutable.
    resp = await client.post(
        f"/admin/rule-sets/{rule_set_id}/rules",
        json={"type": "exclusion", "condition": {"==": [1, 1]}, "effect": {"block": True}},
    )
    assert resp.status_code == 409

    # Re-publish refused.
    resp = await client.post(f"/admin/rule-sets/{rule_set_id}/publish")
    assert resp.status_code == 409


async def test_contradictory_rule_set_refused_at_publish(client):
    template_id = await _build_template(client, "test-bad-rules")
    group_id = await _make_group(client, "test_metal2", ["gold_750"])
    resp = await client.post(
        f"/admin/templates/{template_id}/option-groups",
        json={"option_group_id": group_id, "step_order": 1},
    )
    assert resp.status_code == 201

    resp = await client.post(f"/admin/templates/{template_id}/rule-sets")
    rule_set_id = resp.json()["id"]

    # Blocks everything → simulator must refuse the publish.
    resp = await client.post(
        f"/admin/rule-sets/{rule_set_id}/rules",
        json={
            "type": "exclusion",
            "condition": {"==": [1, 1]},
            "effect": {"block": True},
            "message": "blocks all",
        },
    )
    assert resp.status_code == 201

    resp = await client.post(f"/admin/rule-sets/{rule_set_id}/publish")
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail["report"]["always_blocked"] is True

    # Draft versions increment.
    resp = await client.post(f"/admin/templates/{template_id}/rule-sets")
    assert resp.json()["version"] == 2


async def test_admin_is_tenant_scoped(client):
    resp = await client.get("/admin/templates")
    assert resp.status_code == 200
    codes = {t["code"] for t in resp.json()}
    assert "oval-solitaire" in codes  # seeded demo template visible
