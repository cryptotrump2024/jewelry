"""Group C — Ring-specific (docs/spec/05-data-model.md).

ring_sizes carries tenant_id (queried directly for the configurator);
ring_size_standards is a global conversion map; the rest inherit tenancy via
their template FK.
"""

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class RingSize(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    __tablename__ = "ring_sizes"
    __table_args__ = (UniqueConstraint("tenant_id", "standard", "label"),)

    standard: Mapped[str] = mapped_column(String(10), nullable=False)  # EU|US|UK
    label: Mapped[str] = mapped_column(String(20), nullable=False)
    diameter_mm: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    circumference_mm: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)


class RingSizeStandard(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Global size-conversion map (not tenant data)."""

    __tablename__ = "ring_size_standards"
    __table_args__ = (UniqueConstraint("from_standard", "from_label", "to_standard"),)

    from_standard: Mapped[str] = mapped_column(String(10), nullable=False)
    from_label: Mapped[str] = mapped_column(String(20), nullable=False)
    to_standard: Mapped[str] = mapped_column(String(10), nullable=False)
    to_label: Mapped[str] = mapped_column(String(20), nullable=False)


class TemplateSizeWeightFactor(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Size → metal-weight multiplier (tenancy via template)."""

    __tablename__ = "template_size_weight_factors"
    __table_args__ = (UniqueConstraint("template_id", "ring_size_id"),)

    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ring_size_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ring_sizes.id", ondelete="CASCADE"), nullable=False
    )
    weight_factor: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)


class RingProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Optional band geometry for weight/fit notes (tenancy via template)."""

    __tablename__ = "ring_profiles"

    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    band_width_mm: Mapped[Decimal | None] = mapped_column(Numeric(6, 3), nullable=True)
    band_profile: Mapped[str | None] = mapped_column(String(50), nullable=True)
