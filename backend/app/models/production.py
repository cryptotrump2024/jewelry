"""Group L — Production & QC (docs/spec/05-data-model.md).

hallmark_records gate shipping: a hallmark-required item can't ship without
one (Phase 8 exit test). Children inherit tenancy via production_jobs.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class ProductionJob(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    __tablename__ = "production_jobs"

    order_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("order_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    factory_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("factories.id", ondelete="RESTRICT"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending", index=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    spec_sheet_media_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("media_assets.id", ondelete="SET NULL"), nullable=True
    )
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ProductionStep(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "production_steps"

    production_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("production_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # cad|awaiting_approval|casting|stone_setting|polishing|hallmarking|qc|shipping
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)


class ProductionFile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "production_files"

    production_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("production_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    media_asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("media_assets.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # cad|render|spec|other


class ProductionNote(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "production_notes"

    production_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("production_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    note: Mapped[str] = mapped_column(String(4000), nullable=False)


class QcCheck(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "qc_checks"

    production_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("production_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    checklist: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    checked_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class QcPhoto(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "qc_photos"

    production_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("production_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    media_asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("media_assets.id", ondelete="CASCADE"), nullable=False
    )


class HallmarkRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Dutch/EU hallmarking (docs/spec/12): gold ≥1g, silver ≥8g, Pt ≥0.5g."""

    __tablename__ = "hallmark_records"

    production_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("production_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    metal: Mapped[str | None] = mapped_column(String(30), nullable=True)
    fineness: Mapped[int | None] = mapped_column(Integer, nullable=True)
    responsibility_mark: Mapped[str | None] = mapped_column(String(100), nullable=True)
    assay_office: Mapped[str | None] = mapped_column(
        String(30), nullable=True
    )  # waarborg_holland|ewn|ccm|other
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="not_required"
    )  # not_required|pending|applied
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Shipment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "shipments"

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    carrier: Mapped[str | None] = mapped_column(String(50), nullable=True)
    tracking: Mapped[str | None] = mapped_column(String(255), nullable=True)
    insured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
