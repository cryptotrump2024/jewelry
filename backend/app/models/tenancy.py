"""Group A — Tenancy (docs/spec/05-data-model.md).

tenants is the root table; the other four are tenant-scoped configuration.
"""

from typing import Any

from sqlalchemy import Boolean, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import (
    Base,
    SoftDeleteMixin,
    TenantScopedMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class Tenant(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")

    settings: Mapped[list["TenantSetting"]] = relationship(back_populates="tenant")
    domains: Mapped[list["TenantDomain"]] = relationship(back_populates="tenant")
    locales: Mapped[list["TenantLocale"]] = relationship(back_populates="tenant")
    currencies: Mapped[list["TenantCurrency"]] = relationship(back_populates="tenant")


class TenantSetting(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    __tablename__ = "tenant_settings"
    __table_args__ = (UniqueConstraint("tenant_id", "key"),)

    key: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    tenant: Mapped[Tenant] = relationship(back_populates="settings")


class TenantDomain(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    __tablename__ = "tenant_domains"
    __table_args__ = (UniqueConstraint("host"),)

    host: Mapped[str] = mapped_column(String(255), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    tenant: Mapped[Tenant] = relationship(back_populates="domains")


class TenantLocale(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    __tablename__ = "tenant_locales"
    __table_args__ = (UniqueConstraint("tenant_id", "locale"),)

    locale: Mapped[str] = mapped_column(String(10), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    tenant: Mapped[Tenant] = relationship(back_populates="locales")


class TenantCurrency(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    __tablename__ = "tenant_currencies"
    __table_args__ = (UniqueConstraint("tenant_id", "currency"),)

    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rounding_rule: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    tenant: Mapped[Tenant] = relationship(back_populates="currencies")
