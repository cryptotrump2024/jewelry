"""Seed Group A: the default (own-brand) tenant.

Idempotent — safe to re-run (PRINCIPLES.md: idempotent jobs). Brand name and
domain are deliberately placeholder values: both are open decisions and must
never be hardcoded in the engine (docs/spec/00-project-overview.md §5).
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session_factory
from app.models import Tenant, TenantCurrency, TenantDomain, TenantLocale, TenantSetting

DEFAULT_SETTINGS: dict[str, dict] = {
    "branding": {"display_name": "Default Jewelry Brand (placeholder — decision #1 open)"},
    "feature_flags": {"saas_ui": False, "bespoke": True, "made_to_order": True},
    "defaults": {"market": "NL", "locale": "en", "currency": "EUR"},
}
DEFAULT_LOCALES = [("en", True), ("nl", False)]
DEFAULT_CURRENCIES = [("EUR", True)]
DEFAULT_DOMAINS = [("localhost", True)]


async def _seed(session: AsyncSession) -> Tenant:
    slug = get_settings().default_tenant_slug
    tenant = (
        await session.execute(select(Tenant).where(Tenant.slug == slug))
    ).scalar_one_or_none()
    if tenant is None:
        tenant = Tenant(name="Default Tenant", slug=slug, status="active")
        session.add(tenant)
        await session.flush()

    for key, value in DEFAULT_SETTINGS.items():
        exists = (
            await session.execute(
                select(TenantSetting).where(
                    TenantSetting.tenant_id == tenant.id, TenantSetting.key == key
                )
            )
        ).scalar_one_or_none()
        if exists is None:
            session.add(TenantSetting(tenant_id=tenant.id, key=key, value=value))

    for locale, is_default in DEFAULT_LOCALES:
        exists = (
            await session.execute(
                select(TenantLocale).where(
                    TenantLocale.tenant_id == tenant.id, TenantLocale.locale == locale
                )
            )
        ).scalar_one_or_none()
        if exists is None:
            session.add(TenantLocale(tenant_id=tenant.id, locale=locale, is_default=is_default))

    for currency, is_default in DEFAULT_CURRENCIES:
        exists = (
            await session.execute(
                select(TenantCurrency).where(
                    TenantCurrency.tenant_id == tenant.id,
                    TenantCurrency.currency == currency,
                )
            )
        ).scalar_one_or_none()
        if exists is None:
            session.add(
                TenantCurrency(tenant_id=tenant.id, currency=currency, is_default=is_default)
            )

    for host, is_primary in DEFAULT_DOMAINS:
        exists = (
            await session.execute(select(TenantDomain).where(TenantDomain.host == host))
        ).scalar_one_or_none()
        if exists is None:
            session.add(TenantDomain(tenant_id=tenant.id, host=host, is_primary=is_primary))

    return tenant


async def seed_default_tenant() -> Tenant:
    async with get_session_factory()() as session:
        async with session.begin():
            tenant = await _seed(session)
        return tenant
