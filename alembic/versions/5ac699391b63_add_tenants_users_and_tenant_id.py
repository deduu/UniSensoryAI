"""add_tenants_users_and_tenant_id

Revision ID: 5ac699391b63
Revises: 4f18a84e6d99
Create Date: 2026-05-11 15:29:30.569827

Creates tenants + users tables and adds tenant_id FK to ingestionjobs,
documents, and chatconversations. Existing rows are backfilled to a seed
"default" tenant before tenant_id is flipped to NOT NULL.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '5ac699391b63'
down_revision: Union[str, Sequence[str], None] = '4f18a84e6d99'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SEED_TENANT_ID = "default"
SEED_TENANT_NAME = "Default Tenant"
SEED_TENANT_SLUG = "default"


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "tenants",
        sa.Column("id", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tenants_slug"), "tenants", ["slug"], unique=True)

    op.create_table(
        "users",
        sa.Column("id", sa.String(length=50), nullable=False),
        sa.Column("tenant_id", sa.String(length=50), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("oauth_provider", sa.String(length=32), nullable=False),
        sa.Column("oauth_subject", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("oauth_provider", "oauth_subject", name="uq_users_oauth_identity"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_tenant_id"), "users", ["tenant_id"], unique=False)

    # Seed default tenant so existing rows have an owner to backfill against.
    op.execute(
        sa.text(
            """
            INSERT INTO tenants (id, name, slug, created_at, updated_at)
            VALUES (:id, :name, :slug, NOW(), NOW())
            """
        ).bindparams(id=SEED_TENANT_ID, name=SEED_TENANT_NAME, slug=SEED_TENANT_SLUG)
    )

    # Add tenant_id as nullable first so backfill can populate it.
    op.add_column(
        "ingestionjobs",
        sa.Column("tenant_id", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("tenant_id", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "chatconversations",
        sa.Column("tenant_id", sa.String(length=50), nullable=True),
    )

    # Backfill every pre-existing row to the seed tenant.
    op.execute(
        sa.text("UPDATE ingestionjobs SET tenant_id = :t WHERE tenant_id IS NULL")
        .bindparams(t=SEED_TENANT_ID)
    )
    op.execute(
        sa.text("UPDATE documents SET tenant_id = :t WHERE tenant_id IS NULL")
        .bindparams(t=SEED_TENANT_ID)
    )
    op.execute(
        sa.text("UPDATE chatconversations SET tenant_id = :t WHERE tenant_id IS NULL")
        .bindparams(t=SEED_TENANT_ID)
    )

    # Flip to NOT NULL now that every row has a tenant.
    op.alter_column("ingestionjobs", "tenant_id", existing_type=sa.String(length=50), nullable=False)
    op.alter_column("documents", "tenant_id", existing_type=sa.String(length=50), nullable=False)
    op.alter_column("chatconversations", "tenant_id", existing_type=sa.String(length=50), nullable=False)

    # FKs + indexes for tenant_id on each owned table.
    op.create_foreign_key(
        "fk_ingestionjobs_tenant_id",
        "ingestionjobs",
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        op.f("ix_ingestionjobs_tenant_id"),
        "ingestionjobs",
        ["tenant_id"],
        unique=False,
    )

    op.create_foreign_key(
        "fk_documents_tenant_id",
        "documents",
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        op.f("ix_documents_tenant_id"),
        "documents",
        ["tenant_id"],
        unique=False,
    )

    op.create_foreign_key(
        "fk_chatconversations_tenant_id",
        "chatconversations",
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        op.f("ix_chatconversations_tenant_id"),
        "chatconversations",
        ["tenant_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_chatconversations_tenant_id"), table_name="chatconversations")
    op.drop_constraint("fk_chatconversations_tenant_id", "chatconversations", type_="foreignkey")
    op.drop_column("chatconversations", "tenant_id")

    op.drop_index(op.f("ix_documents_tenant_id"), table_name="documents")
    op.drop_constraint("fk_documents_tenant_id", "documents", type_="foreignkey")
    op.drop_column("documents", "tenant_id")

    op.drop_index(op.f("ix_ingestionjobs_tenant_id"), table_name="ingestionjobs")
    op.drop_constraint("fk_ingestionjobs_tenant_id", "ingestionjobs", type_="foreignkey")
    op.drop_column("ingestionjobs", "tenant_id")

    op.drop_index(op.f("ix_users_tenant_id"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")

    op.drop_index(op.f("ix_tenants_slug"), table_name="tenants")
    op.drop_table("tenants")
