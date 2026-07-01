"""Group I (rest) — Supplier imports, capabilities, overrides
(docs/spec/05-data-model.md).

factory_manufacturability replaces the earlier generic factory_capabilities
key/value idea — build one, not both (audit pass v1.2).
"""

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, Date, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class FactoryManufacturability(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """What each factory can actually make; a config routed to a factory is

    checked against this before the order is accepted.
    """

    __tablename__ = "factory_manufacturability"

    factory_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("factories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    can_cast: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    can_set_stone: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    can_engrave: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    can_prototype: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    supported_metals: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    supported_settings: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    max_stone_carat: Mapped[Decimal | None] = mapped_column(Numeric(6, 3), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)


class SupplierPriceList(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    __tablename__ = "supplier_price_lists"

    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("suppliers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # metal|labor|stone|product
    url_or_ref: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)


class SupplierImportJob(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """Import framework: accepts anything (manual/file/API), dry-run first,

    idempotent commits (docs/spec/09, PRINCIPLES.md idempotent jobs).
    """

    __tablename__ = "supplier_import_jobs"

    supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=True
    )
    source: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # manual|excel|csv|xml|ftp|api|graphql
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    mapping: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    dry_run: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    stats: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)


class SupplierImportRow(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Child of supplier_import_jobs (tenancy via parent)."""

    __tablename__ = "supplier_import_rows"

    import_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("supplier_import_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    raw: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    mapped: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="ok")  # ok|warn|error
    messages: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)


class FactoryProductOverride(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """Per-factory weight/cost overrides — a real factory weight beats the

    CAD volume estimate outright (docs/spec/06 §2).
    """

    __tablename__ = "factory_product_overrides"

    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    factory_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("factories.id", ondelete="CASCADE"), nullable=False
    )
    weight_override_g: Mapped[Decimal | None] = mapped_column(Numeric(8, 3), nullable=True)
    cost_override: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
