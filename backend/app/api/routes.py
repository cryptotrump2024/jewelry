from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db_session
from app.models import TenantCurrency, TenantLocale, TenantSetting
from app.tenancy.context import get_current_tenant
from app.tenancy.repository import TenantScopedRepository

router = APIRouter()

DbSession = Annotated[AsyncSession, Depends(get_db_session)]


@router.get("/health")
async def health(session: DbSession) -> dict[str, Any]:
    await session.execute(select(1))
    return {"status": "ok", "database": "ok"}


class TenantSettingRepository(TenantScopedRepository[TenantSetting]):
    model = TenantSetting


@router.get("/tenant/me")
async def tenant_me(session: DbSession) -> dict[str, Any]:
    """Phase 0 exit-test endpoint: proves a request carries tenant context

    end-to-end — middleware resolved the tenant, and the scoped repository
    reads that tenant's rows without any tenant id in application code.
    """
    ctx = get_current_tenant()
    settings_rows = await TenantSettingRepository(session).list()
    locales = (
        (
            await session.execute(
                select(TenantLocale.locale, TenantLocale.is_default)
                .where(TenantLocale.tenant_id == ctx.tenant_id)
                .order_by(TenantLocale.is_default.desc(), TenantLocale.locale)
            )
        )
        .all()
    )
    currencies = (
        (
            await session.execute(
                select(TenantCurrency.currency, TenantCurrency.is_default)
                .where(TenantCurrency.tenant_id == ctx.tenant_id)
                .order_by(TenantCurrency.is_default.desc(), TenantCurrency.currency)
            )
        )
        .all()
    )
    return {
        "tenant_id": str(ctx.tenant_id),
        "slug": ctx.slug,
        "settings": {row.key: row.value for row in settings_rows},
        "locales": [{"locale": lo, "is_default": d} for lo, d in locales],
        "currencies": [{"currency": c, "is_default": d} for c, d in currencies],
    }
