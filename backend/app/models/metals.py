"""Group D — Metals (docs/spec/05-data-model.md).

material_options is the normalized valid-combination table: the configurator
offers material_options, never free metal x purity x color, so nonsense like
silver+18k or platinum+rose cannot be produced by default.

Tenancy: metals, material_options, metal_price_sources, metal_price_snapshots
and metal_compatibility_rules carry tenant_id (queried directly); purities,
colors and densities inherit via their metal FK.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
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


class Metal(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    __tablename__ = "metals"
    __table_args__ = (UniqueConstraint("tenant_id", "key"),)

    key: Mapped[str] = mapped_column(String(30), nullable=False)  # gold|platinum|silver
    name: Mapped[str] = mapped_column(String(100), nullable=False)


class MetalPurity(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "metal_purities"
    __table_args__ = (UniqueConstraint("metal_id", "fineness"),)

    metal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("metals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    karat: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 14/18/20/22; null for Pt/Ag
    fineness: Mapped[int] = mapped_column(Integer, nullable=False)  # 585/750/833/916/950/925
    label: Mapped[str] = mapped_column(String(50), nullable=False)


class MetalColor(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "metal_colors"
    __table_args__ = (UniqueConstraint("metal_id", "key"),)

    metal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("metals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    key: Mapped[str] = mapped_column(String(20), nullable=False)  # yellow|white|rose
    label: Mapped[str] = mapped_column(String(50), nullable=False)


class MetalDensity(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Casting specific gravity (docs/spec/06-pricing-engine.md §2).

    Factory overrides win over these seeded defaults.
    """

    __tablename__ = "metal_densities"
    __table_args__ = (UniqueConstraint("metal_purity_id", "metal_color_id"),)

    metal_purity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("metal_purities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    metal_color_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("metal_colors.id", ondelete="CASCADE"), nullable=True
    )
    specific_gravity: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    source: Mapped[str | None] = mapped_column(String(255), nullable=True)


class MaterialOption(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """The valid metal+purity+color combinations the configurator may offer."""

    __tablename__ = "material_options"
    __table_args__ = (UniqueConstraint("tenant_id", "metal_id", "purity_id", "color_id"),)

    metal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("metals.id", ondelete="CASCADE"), nullable=False
    )
    purity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("metal_purities.id", ondelete="CASCADE"), nullable=False
    )
    color_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("metal_colors.id", ondelete="CASCADE"), nullable=True
    )
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    fineness: Mapped[int] = mapped_column(Integer, nullable=False)
    density_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("metal_densities.id", ondelete="RESTRICT"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    recommended_for_engagement_rings: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )


class MetalPriceSource(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    __tablename__ = "metal_price_sources"

    provider: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # goldapi|metalsdev|metalpriceapi|manual
    config: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class MetalPriceSnapshot(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """Time series of fetched per-gram prices; the pricing hot path reads the

    freshest row from cache, and price_snapshots pin the exact row used.
    """

    __tablename__ = "metal_price_snapshots"

    metal: Mapped[str] = mapped_column(String(30), nullable=False)
    karat: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    price_per_gram: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MetalCompatibilityRule(
    UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, TenantScopedMixin, Base
):
    __tablename__ = "metal_compatibility_rules"

    rule: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
