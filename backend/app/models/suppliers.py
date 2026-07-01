"""Group I (core) — Suppliers & factories (docs/spec/05-data-model.md).

Only the two tables other groups FK onto; the import framework tables land
with the orders/production slice.
"""

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base,
    SoftDeleteMixin,
    TenantScopedMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class Supplier(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, TenantScopedMixin, Base):
    __tablename__ = "suppliers"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # factory|wholesaler|diamond_feed|gem_feed
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    contact: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    markup_rule: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Factory(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, TenantScopedMixin, Base):
    __tablename__ = "factories"

    supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    capabilities: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    lead_time_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_order: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    handles_hallmarking: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
