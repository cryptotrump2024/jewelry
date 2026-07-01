"""Group G — Rules (docs/spec/05-data-model.md, contract in docs/spec/07).

Rule sets are versioned per template; quotes/orders pin the version they were
priced under. Rules are data (PRINCIPLES.md 2): scope/condition/effect are
JSON-logic evaluated by an allow-listed evaluator (Phase 2).
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class RuleSet(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    __tablename__ = "rule_sets"
    __table_args__ = (UniqueConstraint("tenant_id", "template_id", "version"),)

    template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_templates.id", ondelete="CASCADE"),
        nullable=True,  # null = tenant-global rule set
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    rules: Mapped[list["Rule"]] = relationship(back_populates="rule_set", order_by="Rule.sort")


class Rule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Child of rule_sets (tenancy via parent)."""

    __tablename__ = "rules"

    rule_set_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rule_sets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # compatibility|exclusion|requirement|conditional_visibility|price_modifier
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    scope: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    condition: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    effect: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sort: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    rule_set: Mapped[RuleSet] = relationship(back_populates="rules")


class OptionDependency(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Simple requires/excludes pairs (tenancy via rule set)."""

    __tablename__ = "option_dependencies"

    rule_set_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rule_sets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    when_option_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("options.id", ondelete="CASCADE"), nullable=False
    )
    requires_option_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("options.id", ondelete="CASCADE"), nullable=True
    )
    excludes_option_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("options.id", ondelete="CASCADE"), nullable=True
    )
