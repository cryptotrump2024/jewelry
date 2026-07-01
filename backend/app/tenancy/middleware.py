"""Tenant resolution middleware.

Resolution order (docs/spec/04-architecture.md §5 — tenant resolved by host at
the edge, injected into request context):

1. Exact match of the request host against tenant_domains.
2. Fallback to settings.default_tenant_slug (single-tenant MVP behaviour).

Resolved tenants are cached in-process for a short TTL so the hot path does
not pay a DB lookup per request.
"""

import time

from sqlalchemy import select
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config import get_settings
from app.db import get_session_factory
from app.models import Tenant, TenantDomain
from app.tenancy.context import TenantContext, set_current_tenant

_CACHE_TTL_SECONDS = 60.0
_cache: dict[str, tuple[float, TenantContext]] = {}


def clear_tenant_cache() -> None:
    _cache.clear()


async def resolve_tenant(host: str) -> TenantContext | None:
    cached = _cache.get(host)
    if cached and (time.monotonic() - cached[0]) < _CACHE_TTL_SECONDS:
        return cached[1]

    async with get_session_factory()() as session:
        tenant = (
            await session.execute(
                select(Tenant)
                .join(TenantDomain, TenantDomain.tenant_id == Tenant.id)
                .where(TenantDomain.host == host, Tenant.deleted_at.is_(None))
            )
        ).scalar_one_or_none()

        if tenant is None:
            tenant = (
                await session.execute(
                    select(Tenant).where(
                        Tenant.slug == get_settings().default_tenant_slug,
                        Tenant.deleted_at.is_(None),
                    )
                )
            ).scalar_one_or_none()

    if tenant is None:
        return None

    ctx = TenantContext(tenant_id=tenant.id, slug=tenant.slug)
    _cache[host] = (time.monotonic(), ctx)
    return ctx


class TenantContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        host = (request.headers.get("host") or "").split(":")[0].lower()
        ctx = await resolve_tenant(host)
        if ctx is None:
            return JSONResponse(
                status_code=503,
                content={"detail": "No tenant configured. Run seeds (python -m app.seeds)."},
            )
        set_current_tenant(ctx)
        request.state.tenant = ctx
        try:
            return await call_next(request)
        finally:
            set_current_tenant(None)
