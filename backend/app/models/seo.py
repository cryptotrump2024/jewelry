"""Group N — SEO / GEO (docs/spec/05-data-model.md; engine contract in 11).

SEO/GEO is engine output (PRINCIPLES.md 6). indexable_configurations is the
single deliberate exception to no-SKU-explosion: a curated set of commercial
variants with stable sku/slug/canonical for schema, sitemaps and the feed.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base,
    SoftDeleteMixin,
    TenantScopedMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class SeoPage(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, TenantScopedMixin, Base):
    __tablename__ = "seo_pages"
    __table_args__ = (UniqueConstraint("tenant_id", "slug", "locale", "market"),)

    page_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # template|category|landing|guide
    ref_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    locale: Mapped[str] = mapped_column(String(10), nullable=False)
    market: Mapped[str] = mapped_column(String(10), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    canonical_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    indexable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    follow: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    schema_type: Mapped[str | None] = mapped_column(String(50), nullable=True)


class SeoMetadata(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "seo_metadata"

    seo_page_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("seo_pages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    seo_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    seo_description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    h1: Mapped[str | None] = mapped_column(String(255), nullable=True)
    primary_keyword: Mapped[str | None] = mapped_column(String(255), nullable=True)
    secondary_keywords: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    search_intent: Mapped[str | None] = mapped_column(String(30), nullable=True)


class SeoIndexingRule(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """Pattern-based control of configurator-state indexation."""

    __tablename__ = "seo_indexing_rules"

    pattern: Mapped[str] = mapped_column(String(500), nullable=False)
    indexable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)


class SeoRedirect(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    __tablename__ = "seo_redirects"
    __table_args__ = (UniqueConstraint("tenant_id", "from_path"),)

    from_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    to_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False, default=301)


class SeoInternalLink(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    __tablename__ = "seo_internal_links"

    from_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    to_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    anchor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    context: Mapped[str | None] = mapped_column(String(500), nullable=True)


class HreflangGroup(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    __tablename__ = "hreflang_groups"
    __table_args__ = (UniqueConstraint("tenant_id", "key"),)

    key: Mapped[str] = mapped_column(String(255), nullable=False)


class HreflangUrl(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Note: `en-EU` is not a valid hreflang code — use `en`, `en-NL`, etc."""

    __tablename__ = "hreflang_urls"

    hreflang_group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hreflang_groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    locale: Mapped[str] = mapped_column(String(10), nullable=False)
    market: Mapped[str | None] = mapped_column(String(10), nullable=True)
    url: Mapped[str] = mapped_column(String(1000), nullable=False)


class Sitemap(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    __tablename__ = "sitemaps"

    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # pages|products|images|localized
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SitemapItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sitemap_items"

    sitemap_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sitemaps.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    loc: Mapped[str] = mapped_column(String(1000), nullable=False)
    lastmod: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    changefreq: Mapped[str | None] = mapped_column(String(20), nullable=True)
    priority: Mapped[str | None] = mapped_column(String(5), nullable=True)
    images: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)


class ContentBlock(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    __tablename__ = "content_blocks"

    ref_type: Mapped[str] = mapped_column(String(30), nullable=False)
    ref_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    locale: Mapped[str] = mapped_column(String(10), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # intro|trust|guide|expert_note
    body: Mapped[str] = mapped_column(String(20000), nullable=False)
    sort: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class FaqBlock(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    __tablename__ = "faq_blocks"

    ref_type: Mapped[str] = mapped_column(String(30), nullable=False)
    ref_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    locale: Mapped[str] = mapped_column(String(10), nullable=False)
    question: Mapped[str] = mapped_column(String(500), nullable=False)
    answer: Mapped[str] = mapped_column(String(5000), nullable=False)
    sort: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class AnswerBlock(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """GEO: concise answers structured for AI-search extraction."""

    __tablename__ = "answer_blocks"

    topic: Mapped[str] = mapped_column(String(255), nullable=False)
    locale: Mapped[str] = mapped_column(String(10), nullable=False)
    question: Mapped[str] = mapped_column(String(500), nullable=False)
    concise_answer: Mapped[str] = mapped_column(String(2000), nullable=False)
    supporting: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)


class TopicCluster(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    __tablename__ = "topic_clusters"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    pillar_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    members: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)


class ImageMetadata(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "image_metadata"

    media_asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("media_assets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    alt: Mapped[str | None] = mapped_column(String(500), nullable=True)
    caption: Mapped[str | None] = mapped_column(String(500), nullable=True)
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)


class IndexableConfiguration(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """Curated commercial/SEO variants — the deliberate exception to

    "don't persist variants". sku == schema variant sku == feed id;
    template.code == schema productGroupID == feed item_group_id.
    """

    __tablename__ = "indexable_configurations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "sku"),
        UniqueConstraint("tenant_id", "template_id", "config_hash", "market", "locale"),
    )

    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    config_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    sku: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    selections: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    market: Mapped[str] = mapped_column(String(10), nullable=False)
    locale: Mapped[str] = mapped_column(String(10), nullable=False)
    indexable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    merchant_feed_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    canonical_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    price_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("price_snapshots.id", ondelete="SET NULL"), nullable=True
    )
