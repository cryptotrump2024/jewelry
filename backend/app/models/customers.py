"""Group M — Customers & auth (docs/spec/05-data-model.md).

consents is GDPR groundwork; addresses inherit tenancy via customer.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base,
    SoftDeleteMixin,
    TenantScopedMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class Customer(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, TenantScopedMixin, Base):
    __tablename__ = "customers"
    __table_args__ = (UniqueConstraint("tenant_id", "email"),)

    email: Mapped[str] = mapped_column(String(320), nullable=False)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    locale: Mapped[str | None] = mapped_column(String(10), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    marketing_consent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Address(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "addresses"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # billing|shipping
    fields: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    country: Mapped[str] = mapped_column(String(2), nullable=False)


class User(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, TenantScopedMixin, Base):
    """Staff/portal users (admin, factory, finance...)."""

    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("tenant_id", "email"),)

    email: Mapped[str] = mapped_column(String(320), nullable=False)
    role: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # admin|editor|merchandiser|factory|finance|tenant_admin
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")


class Consent(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """GDPR consent log (subject may be a customer or a user)."""

    __tablename__ = "consents"

    subject_type: Mapped[str] = mapped_column(String(20), nullable=False)  # customer|user
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)  # gdpr_terms|marketing|cookies
    granted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
