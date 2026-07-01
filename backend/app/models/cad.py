"""Group F — CAD / visual (docs/spec/05-data-model.md).

future_3d_assets is deliberately schema-ready for the interactive-3D phase.
"""

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class CadFile(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    __tablename__ = "cad_files"

    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    component_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("template_components.id", ondelete="CASCADE"), nullable=True
    )
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    format: Mapped[str] = mapped_column(String(10), nullable=False)  # 3dm|stl|step|glb
    volume_mm3: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)


class RenderJob(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    __tablename__ = "render_jobs"

    config_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    input: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    output_media_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("media_assets.id", ondelete="SET NULL"), nullable=True
    )


class Future3DAsset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """LATER — interactive 3D (tenancy via template)."""

    __tablename__ = "future_3d_assets"

    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    glb_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    material_map: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    mesh_map: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
