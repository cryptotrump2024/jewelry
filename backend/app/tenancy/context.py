"""Per-request tenant context.

The middleware resolves the tenant and sets it here; everything downstream
(repositories, services, jobs) reads it via get_current_tenant() instead of
passing tenant ids by hand. No query may ever cross tenants (PRINCIPLES.md 5).
"""

import uuid
from contextvars import ContextVar
from dataclasses import dataclass


@dataclass(frozen=True)
class TenantContext:
    tenant_id: uuid.UUID
    slug: str


_current_tenant: ContextVar[TenantContext | None] = ContextVar("current_tenant", default=None)


def set_current_tenant(ctx: TenantContext | None) -> None:
    _current_tenant.set(ctx)


def get_current_tenant() -> TenantContext:
    ctx = _current_tenant.get()
    if ctx is None:
        raise RuntimeError(
            "No tenant in context. Requests must pass through TenantContextMiddleware; "
            "background jobs must set the tenant explicitly."
        )
    return ctx
