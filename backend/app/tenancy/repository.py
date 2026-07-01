"""Tenant-scoped repository base.

Every business-table query goes through a repository built on this class so
tenant filtering cannot be forgotten. Raw unscoped queries on tenant tables
are a review-blocking offence (PRINCIPLES.md rule 5).
"""

import uuid
from typing import Any, Generic, TypeVar

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.tenancy.context import get_current_tenant

ModelT = TypeVar("ModelT")


class TenantScopedRepository(Generic[ModelT]):
    """Base repository whose every query is filtered by the current tenant.

    Subclasses set `model` to a mapped class that carries `tenant_id`
    (TenantScopedMixin). The tenant comes from the request context by default
    so application code cannot pass the wrong one.
    """

    model: type[ModelT]

    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID | None = None):
        self.session = session
        self._tenant_id = tenant_id

    @property
    def tenant_id(self) -> uuid.UUID:
        if self._tenant_id is not None:
            return self._tenant_id
        return get_current_tenant().tenant_id

    def query(self) -> Select[tuple[ModelT]]:
        """Starting point for every read: pre-filtered by tenant."""
        return select(self.model).where(self.model.tenant_id == self.tenant_id)

    async def get(self, entity_id: uuid.UUID) -> ModelT | None:
        result = await self.session.execute(self.query().where(self.model.id == entity_id))
        return result.scalar_one_or_none()

    async def list(self) -> list[ModelT]:
        result = await self.session.execute(self.query())
        return list(result.scalars().all())

    def create(self, **kwargs: Any) -> ModelT:
        """Instantiate with the current tenant stamped on; caller commits."""
        kwargs.setdefault("tenant_id", self.tenant_id)
        if kwargs["tenant_id"] != self.tenant_id:
            raise ValueError("Attempt to create a row for a different tenant.")
        entity = self.model(**kwargs)
        self.session.add(entity)
        return entity
