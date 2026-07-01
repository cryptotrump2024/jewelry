"""Group E — Stones (docs/spec/05-data-model.md).

MVP prices come from admin-entered diamond_price_tables + carat_price_bands
(magic sizes); supplier_stones is feed-populated LATER without schema change.

Tenancy: stone_types, stone_shapes, price tables, carat bands and
supplier_stones carry tenant_id; quality grades and certificates inherit via
parent FK.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base,
    SoftDeleteMixin,
    TenantScopedMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class StoneType(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    __tablename__ = "stone_types"
    __table_args__ = (UniqueConstraint("tenant_id", "key"),)

    key: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # natural_diamond|lab_diamond|sapphire|ruby|emerald
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class StoneShape(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    __tablename__ = "stone_shapes"
    __table_args__ = (UniqueConstraint("tenant_id", "key"),)

    key: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # round|oval|pear|princess|emerald|cushion|marquise|asscher|radiant
    name: Mapped[str] = mapped_column(String(100), nullable=False)


class StoneQualityGrade(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Ordered grades per attribute (color D..Z, clarity FL..I3, cut...)."""

    __tablename__ = "stone_quality_grades"
    __table_args__ = (UniqueConstraint("stone_type_id", "attribute", "code"),)

    stone_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stone_types.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    attribute: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # color|clarity|cut|polish|symmetry|fluorescence
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    sort: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class DiamondPriceTable(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """Admin-entered per-carat prices by shape/carat band/color/clarity."""

    __tablename__ = "diamond_price_tables"

    stone_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stone_types.id", ondelete="CASCADE"), nullable=False
    )
    shape_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stone_shapes.id", ondelete="CASCADE"), nullable=False
    )
    carat_min: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    carat_max: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    color: Mapped[str] = mapped_column(String(10), nullable=False)
    clarity: Mapped[str] = mapped_column(String(10), nullable=False)
    price_per_carat: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True
    )
    valid_from: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    valid_to: Mapped[datetime | None] = mapped_column(Date, nullable=True)


class GemstonePriceTable(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """LATER — schema-ready for sapphire/ruby/emerald."""

    __tablename__ = "gemstone_price_tables"

    stone_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stone_types.id", ondelete="CASCADE"), nullable=False
    )
    shape_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stone_shapes.id", ondelete="CASCADE"), nullable=False
    )
    carat_min: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    carat_max: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    grade: Mapped[str] = mapped_column(String(20), nullable=False)
    price_per_carat: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)


class CaratPriceBand(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """Magic-size multipliers: crossing 1.00/1.50/2.00 ct jumps the per-carat

    price (docs/spec/06-pricing-engine.md §3) — diamond pricing is non-linear.
    """

    __tablename__ = "carat_price_bands"
    __table_args__ = (UniqueConstraint("tenant_id", "stone_type_id", "carat_threshold"),)

    stone_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stone_types.id", ondelete="CASCADE"), nullable=False
    )
    carat_threshold: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    multiplier: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)


class SupplierStone(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, TenantScopedMixin, Base):
    """Feed-populated inventory (Nivoda et al.) — LATER, schema-ready now."""

    __tablename__ = "supplier_stones"
    __table_args__ = (UniqueConstraint("tenant_id", "supplier_id", "external_id"),)

    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False
    )
    stone_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stone_types.id", ondelete="RESTRICT"), nullable=False
    )
    shape_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stone_shapes.id", ondelete="RESTRICT"), nullable=False
    )
    carat: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    color: Mapped[str | None] = mapped_column(String(10), nullable=True)
    clarity: Mapped[str | None] = mapped_column(String(10), nullable=True)
    cut: Mapped[str | None] = mapped_column(String(20), nullable=True)
    polish: Mapped[str | None] = mapped_column(String(20), nullable=True)
    symmetry: Mapped[str | None] = mapped_column(String(20), nullable=True)
    fluorescence: Mapped[str | None] = mapped_column(String(20), nullable=True)
    cert_lab: Mapped[str | None] = mapped_column(String(20), nullable=True)
    cert_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    cert_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    measurements: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ratio: Mapped[Decimal | None] = mapped_column(Numeric(5, 3), nullable=True)
    depth_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    table_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    availability: Mapped[str | None] = mapped_column(String(30), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    video_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    external_id: Mapped[str] = mapped_column(String(100), nullable=False)
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class StoneCertificate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "stone_certificates"

    supplier_stone_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("supplier_stones.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lab: Mapped[str] = mapped_column(String(20), nullable=False)
    number: Mapped[str] = mapped_column(String(50), nullable=False)
    url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
