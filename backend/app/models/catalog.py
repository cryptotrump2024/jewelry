"""Group B — Catalog & templates (docs/spec/05-data-model.md).

Design rule: templates + options + rules, never generated variants
(PRINCIPLES.md 3). Tenant scoping policy: aggregate roots (categories,
product_templates, option_groups, media_assets) carry tenant_id; pure child
rows (components, manufacturability, options, join tables, media links)
inherit tenancy through their parent FK.
"""

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import (
    Base,
    SoftDeleteMixin,
    TenantScopedMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class Category(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, TenantScopedMixin, Base):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("tenant_id", "slug"),)

    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str | None] = mapped_column(String(50), nullable=True)


class ProductTemplate(
    UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, TenantScopedMixin, Base
):
    """The ProductGroup: a configurable ring model, e.g. "Oval Solitaire"."""

    __tablename__ = "product_templates"
    __table_args__ = (UniqueConstraint("tenant_id", "code"),)

    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    style: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    base_config: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    default_supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True
    )
    is_bespoke_base: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    components: Mapped[list["TemplateComponent"]] = relationship(
        back_populates="template", order_by="TemplateComponent.sort"
    )
    option_group_links: Mapped[list["TemplateOptionGroup"]] = relationship(
        back_populates="template", order_by="TemplateOptionGroup.step_order"
    )


class TemplateComponent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Child of product_templates (tenancy via parent)."""

    __tablename__ = "template_components"

    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # shank|head|prongs|center_stone|side_stones|halo|gallery|engraving_surface|prototype
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    cad_volume_mm3: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    metal_assignable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sort: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    template: Mapped[ProductTemplate] = relationship(back_populates="components")


class TemplateManufacturability(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Hard manufacturing limits per template/component (tenancy via parent).

    Enforced at validate/price time and again at CAD so the configurator/AI
    can't produce a beautiful-but-impossible design.
    """

    __tablename__ = "template_manufacturability"

    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    component_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("template_components.id", ondelete="CASCADE"), nullable=True
    )
    min_band_thickness_mm: Mapped[Decimal | None] = mapped_column(Numeric(6, 3), nullable=True)
    min_wall_thickness_mm: Mapped[Decimal | None] = mapped_column(Numeric(6, 3), nullable=True)
    min_prong_thickness_mm: Mapped[Decimal | None] = mapped_column(Numeric(6, 3), nullable=True)
    prong_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    setting_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    stone_seat_tolerance_mm: Mapped[Decimal | None] = mapped_column(Numeric(6, 3), nullable=True)
    stone_measurement_min_mm: Mapped[Decimal | None] = mapped_column(Numeric(6, 3), nullable=True)
    stone_measurement_max_mm: Mapped[Decimal | None] = mapped_column(Numeric(6, 3), nullable=True)
    requires_manual_cad_check: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )


class OptionGroup(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, TenantScopedMixin, Base):
    __tablename__ = "option_groups"
    __table_args__ = (UniqueConstraint("tenant_id", "key"),)

    # metal|purity|metal_color|finish|stone_type|stone_shape|stone_quality|
    # carat|ring_size|engraving|side_stone|setting
    key: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    ui_type: Mapped[str] = mapped_column(String(20), nullable=False, default="select")
    sort: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    options: Mapped[list["Option"]] = relationship(
        back_populates="group", order_by="Option.sort"
    )


class Option(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Child of option_groups (tenancy via parent)."""

    __tablename__ = "options"
    __table_args__ = (UniqueConstraint("option_group_id", "code"),)

    option_group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("option_groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    sort: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    group: Mapped[OptionGroup] = relationship(back_populates="options")


class TemplateOptionGroup(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Which option groups a template offers, in step order (tenancy via parent)."""

    __tablename__ = "template_option_groups"
    __table_args__ = (UniqueConstraint("template_id", "option_group_id"),)

    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    option_group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("option_groups.id", ondelete="CASCADE"), nullable=False
    )
    step_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    default_option_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("options.id", ondelete="SET NULL"), nullable=True
    )
    min_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)

    template: Mapped[ProductTemplate] = relationship(back_populates="option_group_links")
    option_group: Mapped[OptionGroup] = relationship()


class TemplateComponentOption(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Which components an option group applies to, e.g. metal per component."""

    __tablename__ = "template_component_options"
    __table_args__ = (UniqueConstraint("template_component_id", "option_group_id"),)

    template_component_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("template_components.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    option_group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("option_groups.id", ondelete="CASCADE"), nullable=False
    )


class MediaAsset(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, TenantScopedMixin, Base):
    __tablename__ = "media_assets"

    kind: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # static_angle|ai_render|cad|prototype_stl|texture|env_map
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class TemplateMedia(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "template_media"

    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    media_asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("media_assets.id", ondelete="CASCADE"), nullable=False
    )
    purpose: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sort: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class OptionMediaMap(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Which asset to show for an option (image-swap previews)."""

    __tablename__ = "option_media_map"

    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    option_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("options.id", ondelete="CASCADE"), nullable=False
    )
    media_asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("media_assets.id", ondelete="CASCADE"), nullable=False
    )
