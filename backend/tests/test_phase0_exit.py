"""Phase 0 exit test (docs/spec/14-roadmap-and-open-decisions.md):

  "a request carries a tenant context end-to-end; migrations + seeds run clean."

Migrations + seeds running clean is enforced by the session fixture itself —
if either fails, every test here errors out.
"""

import uuid

import pytest
from sqlalchemy import select

from app.db import get_session_factory
from app.models import Tenant, TenantSetting
from app.tenancy.context import TenantContext, get_current_tenant, set_current_tenant
from app.tenancy.repository import TenantScopedRepository


async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "database": "ok"}


async def test_request_carries_tenant_context_end_to_end(client):
    resp = await client.get("/tenant/me")
    assert resp.status_code == 200
    body = resp.json()
    assert body["slug"] == "default"
    assert uuid.UUID(body["tenant_id"])
    # Seeded data came back through the tenant-scoped repository.
    assert body["settings"]["defaults"] == {"market": "NL", "locale": "en", "currency": "EUR"}
    assert {lo["locale"] for lo in body["locales"]} == {"en", "nl"}
    assert body["currencies"][0] == {"currency": "EUR", "is_default": True}


async def test_seeds_are_idempotent():
    from app.seeds.tenancy import seed_default_tenant

    await seed_default_tenant()
    await seed_default_tenant()
    async with get_session_factory()() as session:
        tenants = (
            (await session.execute(select(Tenant).where(Tenant.slug == "default")))
            .scalars()
            .all()
        )
        assert len(tenants) == 1


async def test_domain_resolution_beats_default(client):
    """The default tenant also owns host `localhost` via tenant_domains."""
    resp = await client.get("/tenant/me", headers={"host": "localhost:8000"})
    assert resp.status_code == 200
    assert resp.json()["slug"] == "default"


async def test_unknown_host_falls_back_to_default_tenant(client):
    resp = await client.get("/tenant/me", headers={"host": "unknown.example.com"})
    assert resp.status_code == 200
    assert resp.json()["slug"] == "default"


class SettingRepo(TenantScopedRepository[TenantSetting]):
    model = TenantSetting


async def test_repository_never_crosses_tenants():
    """Rows belonging to another tenant are invisible through the repository."""
    async with get_session_factory()() as session:
        default_tenant = (
            await session.execute(select(Tenant).where(Tenant.slug == "default"))
        ).scalar_one()
        other = Tenant(name="Other Tenant", slug=f"other-{uuid.uuid4().hex[:8]}", status="active")
        session.add(other)
        await session.flush()
        session.add(TenantSetting(tenant_id=other.id, key="branding", value={"x": 1}))
        await session.commit()

        set_current_tenant(TenantContext(tenant_id=other.id, slug=other.slug))
        try:
            other_rows = await SettingRepo(session).list()
            assert {r.key for r in other_rows} == {"branding"}
            assert all(r.tenant_id == other.id for r in other_rows)

            set_current_tenant(
                TenantContext(tenant_id=default_tenant.id, slug=default_tenant.slug)
            )
            default_rows = await SettingRepo(session).list()
            assert all(r.tenant_id == default_tenant.id for r in default_rows)
        finally:
            set_current_tenant(None)


async def test_repository_refuses_wrong_tenant_writes():
    async with get_session_factory()() as session:
        default_tenant = (
            await session.execute(select(Tenant).where(Tenant.slug == "default"))
        ).scalar_one()
        set_current_tenant(TenantContext(tenant_id=default_tenant.id, slug="default"))
        try:
            with pytest.raises(ValueError, match="different tenant"):
                SettingRepo(session).create(tenant_id=uuid.uuid4(), key="k", value={})
        finally:
            set_current_tenant(None)


async def test_no_context_raises_loudly():
    set_current_tenant(None)
    with pytest.raises(RuntimeError, match="No tenant in context"):
        get_current_tenant()
