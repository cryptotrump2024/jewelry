"""Group K — Orders & payments (docs/spec/05-data-model.md).

Configurations are computed on demand; only *ordered* configurations persist
(PRINCIPLES.md 3). Every order item points at its immutable price snapshot.
withdrawal_requests backs the mandatory EU withdrawal function (Art. 11a, in
force 19 June 2026) — bespoke/engraved items are exempt but the function must
exist for eligible items (docs/spec/12 §3a).
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base,
    SoftDeleteMixin,
    TenantScopedMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class Cart(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, TenantScopedMixin, Base):
    __tablename__ = "carts"

    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="SET NULL"), nullable=True
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    market: Mapped[str] = mapped_column(String(10), nullable=False)


class CartItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "cart_items"

    cart_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("carts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("product_templates.id", ondelete="CASCADE"), nullable=False
    )
    configuration: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    price_calculation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("price_calculations.id", ondelete="SET NULL"), nullable=True
    )
    qty: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class Quote(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    __tablename__ = "quotes"

    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="SET NULL"), nullable=True
    )
    configuration: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    price_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("price_snapshots.id", ondelete="RESTRICT"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Order(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    __tablename__ = "orders"

    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="RESTRICT"), nullable=True
    )
    type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # made_to_order|bespoke|ready_made|prototype
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending", index=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    market: Mapped[str] = mapped_column(String(10), nullable=False)
    totals: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    placed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OrderItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "order_items"

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_templates.id", ondelete="RESTRICT"),
        nullable=True,  # null for pure bespoke
    )
    configuration: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    price_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("price_snapshots.id", ondelete="RESTRICT"), nullable=False
    )
    engraving_text: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ring_size_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ring_sizes.id", ondelete="RESTRICT"), nullable=True
    )
    stone_ref: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    non_returnable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    qty: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class OrderConfiguration(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Fully resolved factory spec for an order item."""

    __tablename__ = "order_configurations"

    order_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("order_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    resolved_spec: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class Payment(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    __tablename__ = "payments"

    order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="SET NULL"), nullable=True
    )
    bespoke_request_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bespoke_requests.id", ondelete="SET NULL"), nullable=True
    )
    psp: Mapped[str] = mapped_column(String(20), nullable=False)  # mollie|stripe|adyen
    psp_ref: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    kind: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # deposit_design|deposit_production|balance|full|prototype
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")


class Deposit(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "deposits"

    order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=True, index=True
    )
    bespoke_request_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bespoke_requests.id", ondelete="CASCADE"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    credited_to_order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="SET NULL"), nullable=True
    )


class Refund(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "refunds"

    payment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("payments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")


class WithdrawalRequest(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """EU Art. 11a two-step withdrawal function: submitted → confirmed, then

    acknowledged on a durable medium. Eligibility derives from
    order_items.non_returnable (bespoke/engraved = exempt).
    """

    __tablename__ = "withdrawal_requests"

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="SET NULL"), nullable=True
    )
    eligibility_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="unknown"
    )  # eligible|exempt_custom|exempt_personalised|unknown
    reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ack_medium: Mapped[str | None] = mapped_column(String(20), nullable=True)  # email|account
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="initiated"
    )  # initiated|confirmed|acknowledged|refunded
