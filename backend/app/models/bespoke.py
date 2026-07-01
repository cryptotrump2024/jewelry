"""Group J — Bespoke (docs/spec/05-data-model.md; workflow in docs/spec/10).

Customer idea → design deposit → CAD/render revisions → approval → order.
Children of bespoke_requests inherit tenancy via parent FK.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class BespokeRequest(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    __tablename__ = "bespoke_requests"

    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="SET NULL"), nullable=True
    )
    source: Mapped[str] = mapped_column(String(20), nullable=False)  # upload|ai_designer
    brief: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="new")
    price_range_min_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    price_range_max_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)


class BespokeUpload(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "bespoke_uploads"

    bespoke_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bespoke_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    media_asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("media_assets.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # photo|sketch|inspiration|existing_jewelry


class BespokeQuote(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "bespoke_quotes"

    bespoke_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bespoke_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    itemized: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    total_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BespokeDeposit(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "bespoke_deposits"

    bespoke_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bespoke_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    payment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payments.id", ondelete="SET NULL"), nullable=True
    )
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    non_refundable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    credited: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class BespokeRevision(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "bespoke_revisions"

    bespoke_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bespoke_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    round_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    cad_media_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("media_assets.id", ondelete="SET NULL"), nullable=True
    )
    render_media_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("media_assets.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="sent"
    )  # sent|approved|revision_requested
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)


class BespokeApproval(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "bespoke_approvals"

    bespoke_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bespoke_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    approved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    becomes_order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="SET NULL"), nullable=True
    )
