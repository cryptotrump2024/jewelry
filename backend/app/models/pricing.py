"""Group H — Pricing (docs/spec/05-data-model.md; contract in docs/spec/06).

Money: integer minor units + currency (never floats — PRINCIPLES.md).
price_snapshots is immutable and fully version-pinned: every input that can
drift (formula, rule set, density, labor, margin, VAT + the exact metal/FX
snapshot rows) is referenced so a historical order reproduces byte-for-byte.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
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


class PriceFormula(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """Ordered price components + how each is computed; versioned."""

    __tablename__ = "price_formula"

    template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_templates.id", ondelete="CASCADE"),
        nullable=True,  # null = tenant default formula
    )
    components: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class LaborCost(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, TenantScopedMixin, Base):
    __tablename__ = "labor_costs"

    operation: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # setting|casting|polishing|finishing|assembly
    basis: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # per_piece|per_stone|per_hour|per_gram
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=True
    )


class SettingCost(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, TenantScopedMixin, Base):
    __tablename__ = "setting_costs"

    setting_type: Mapped[str] = mapped_column(String(50), nullable=False)  # prong|pave|bezel|...
    per_stone_cost_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)


class EngravingCost(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, TenantScopedMixin, Base):
    __tablename__ = "engraving_costs"

    type: Mapped[str] = mapped_column(String(20), nullable=False)  # standard|special
    base_cost_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    per_char_cost_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    makes_non_returnable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class PrototypeCost(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, TenantScopedMixin, Base):
    __tablename__ = "prototype_costs"

    kind: Mapped[str] = mapped_column(String(30), nullable=False, default="plastic_stl")
    base_cost_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    credited_above_order_value_minor: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )


class DesignFee(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, TenantScopedMixin, Base):
    __tablename__ = "design_fees"

    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    refundable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    credited: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Margin(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, TenantScopedMixin, Base):
    """Resolvable per template/market/price-band; percent or fixed."""

    __tablename__ = "margins"

    template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("product_templates.id", ondelete="CASCADE"), nullable=True
    )
    market: Mapped[str | None] = mapped_column(String(10), nullable=True)
    band: Mapped[str | None] = mapped_column(String(30), nullable=True)
    type: Mapped[str] = mapped_column(String(10), nullable=False)  # percent|fixed
    value: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)


class Buffer(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, TenantScopedMixin, Base):
    __tablename__ = "buffers"

    kind: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # shipping|payment_fee|production_risk|warranty
    type: Mapped[str] = mapped_column(String(10), nullable=False)  # percent|fixed
    value: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)  # for fixed


class VatRule(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, TenantScopedMixin, Base):
    __tablename__ = "vat_rules"

    market: Mapped[str] = mapped_column(String(10), nullable=False)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    rate: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    price_includes_vat: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class FxRate(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """Time series (ECB reference rates); snapshots pin the exact row used."""

    __tablename__ = "fx_rates"

    base_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    quote_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PriceCalculation(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """Ephemeral cache keyed by config_hash — advisory only, never checkout."""

    __tablename__ = "price_calculations"

    config_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    itemized: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    total_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PriceSnapshot(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """IMMUTABLE. Written at quote/order time; self-contained and reproducible.

    quote_id / order_item_id FKs are added in the orders migration (0005) to
    avoid a circular dependency — the columns exist from day one.
    """

    __tablename__ = "price_snapshots"

    quote_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    order_item_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    inputs: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    itemized: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    total_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    metal_prices: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    fx_rate: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    stone_price: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    margin_applied: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    vat_applied: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # Version pinning — every drifting input (docs/spec/06 §5).
    template_version: Mapped[int] = mapped_column(Integer, nullable=False)
    price_formula_version: Mapped[int] = mapped_column(Integer, nullable=False)
    rule_set_version: Mapped[int] = mapped_column(Integer, nullable=False)
    density_source_version: Mapped[int] = mapped_column(Integer, nullable=False)
    labor_cost_version: Mapped[int] = mapped_column(Integer, nullable=False)
    margin_rule_version: Mapped[int] = mapped_column(Integer, nullable=False)
    vat_rule_version: Mapped[int] = mapped_column(Integer, nullable=False)
    metal_price_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("metal_price_snapshots.id", ondelete="RESTRICT"),
        nullable=True,
    )
    fx_rate_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fx_rates.id", ondelete="RESTRICT"), nullable=True
    )
