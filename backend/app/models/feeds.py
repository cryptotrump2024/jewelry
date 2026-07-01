"""Group O — Merchant feeds (docs/spec/05-data-model.md).

Feed availability accepts ONLY in_stock/out_of_stock/preorder/backorder —
`MadeToOrder` is a schema.org value, never a feed value. For GTIN-less
made-to-order rings: identifier_exists=false and omit gtin/mpn/brand.
"""

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class MerchantFeed(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    __tablename__ = "merchant_feeds"
    __table_args__ = (UniqueConstraint("tenant_id", "channel", "market", "locale", "currency"),)

    channel: Mapped[str] = mapped_column(String(20), nullable=False, default="google")
    market: Mapped[str] = mapped_column(String(10), nullable=False)
    locale: Mapped[str] = mapped_column(String(10), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MerchantFeedItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "merchant_feed_items"
    __table_args__ = (UniqueConstraint("merchant_feed_id", "offer_id"),)

    merchant_feed_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("merchant_feeds.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    offer_id: Mapped[str] = mapped_column(String(100), nullable=False)  # == sku
    item_group_id: Mapped[str] = mapped_column(String(100), nullable=False)  # == template.code
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(String(5000), nullable=True)
    link: Mapped[str] = mapped_column(String(1000), nullable=False)
    image_link: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    additional_image_link: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    price_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sale_price_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    # in_stock|out_of_stock|preorder|backorder — never MadeToOrder
    availability: Mapped[str] = mapped_column(String(20), nullable=False)
    availability_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    condition: Mapped[str] = mapped_column(String(20), nullable=False, default="new")
    brand: Mapped[str | None] = mapped_column(String(70), nullable=True)
    gtin: Mapped[str | None] = mapped_column(String(50), nullable=True)
    mpn: Mapped[str | None] = mapped_column(String(70), nullable=True)
    identifier_exists: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    google_product_category: Mapped[str | None] = mapped_column(String(255), nullable=True)
    material: Mapped[str | None] = mapped_column(String(100), nullable=True)
    color: Mapped[str | None] = mapped_column(String(100), nullable=True)
    size: Mapped[str | None] = mapped_column(String(20), nullable=True)  # ring size
    custom_label_0: Mapped[str | None] = mapped_column(String(100), nullable=True)
    custom_label_1: Mapped[str | None] = mapped_column(String(100), nullable=True)
    custom_label_2: Mapped[str | None] = mapped_column(String(100), nullable=True)
    custom_label_3: Mapped[str | None] = mapped_column(String(100), nullable=True)
    custom_label_4: Mapped[str | None] = mapped_column(String(100), nullable=True)
    shipping_label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    return_policy_label: Mapped[str | None] = mapped_column(String(100), nullable=True)


class MerchantFeedRule(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    __tablename__ = "merchant_feed_rules"

    rule: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class MerchantCategoryMapping(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    __tablename__ = "merchant_category_mappings"
    __table_args__ = (UniqueConstraint("tenant_id", "internal_category_id"),)

    internal_category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id", ondelete="CASCADE"), nullable=False
    )
    google_product_category: Mapped[str] = mapped_column(String(255), nullable=False)
