"""Group A — Tenancy: tenants, tenant_settings, tenant_domains, tenant_locales,
tenant_currencies (docs/spec/05-data-model.md).

Tenant-scoping policy: all four child tables here are queried/filtered
directly (tenant resolution, settings lookup), so each carries a denormalized
tenant_id per the explicit scoping rule in the data-model doc.

Revision ID: 0001
Revises:
Create Date: 2026-07-01

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _uuid_pk() -> sa.Column:
    return sa.Column("id", UUID(as_uuid=True), primary_key=True)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    ]


def _tenant_fk() -> sa.Column:
    return sa.Column(
        "tenant_id",
        UUID(as_uuid=True),
        sa.ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )


def upgrade() -> None:
    op.create_table(
        "tenants",
        _uuid_pk(),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("status", sa.String(20), nullable=False),
        *_timestamps(),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "tenant_settings",
        _uuid_pk(),
        _tenant_fk(),
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("value", JSONB, nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("tenant_id", "key"),
    )

    op.create_table(
        "tenant_domains",
        _uuid_pk(),
        _tenant_fk(),
        sa.Column("host", sa.String(255), nullable=False, unique=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        *_timestamps(),
    )

    op.create_table(
        "tenant_locales",
        _uuid_pk(),
        _tenant_fk(),
        sa.Column("locale", sa.String(10), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("tenant_id", "locale"),
    )

    op.create_table(
        "tenant_currencies",
        _uuid_pk(),
        _tenant_fk(),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("rounding_rule", JSONB, nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("tenant_id", "currency"),
    )


def downgrade() -> None:
    op.drop_table("tenant_currencies")
    op.drop_table("tenant_locales")
    op.drop_table("tenant_domains")
    op.drop_table("tenant_settings")
    op.drop_table("tenants")
