"""Add independent immutable PAPER source document drafts.

Revision ID: a1090c3d67ef
Revises: dc728f04a912
Create Date: 2026-10-18
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a1090c3d67ef"
down_revision: str | Sequence[str] | None = "dc728f04a912"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add draft headers and immutable source review versions only."""
    op.create_table(
        "paperdocumentdrafts",
        sa.Column("id", sa.String(50), nullable=False),
        sa.Column("tenant_id", sa.String(50), nullable=False),
        sa.Column("role", sa.String(40), nullable=False),
        sa.Column("latest_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_paperdraft_tenant_id"),
        sa.CheckConstraint("latest_version >= 1", name="ck_paperdraft_latest"),
        sa.CheckConstraint(
            "role IN ('rent_invoice','tax_invoice','utility_statement','supporting_document')",
            name="ck_paperdraft_role",
        ),
    )
    op.create_index("ix_paperdocumentdrafts_tenant_id", "paperdocumentdrafts", ["tenant_id"])
    op.create_table(
        "paperdocumentdraftversions",
        sa.Column("tenant_id", sa.String(50), nullable=False),
        sa.Column("draft_id", sa.String(50), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("document", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("search_text", sa.Text(), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("reviewed_by", sa.String(255), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("tenant_id", "draft_id", "version_number"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "draft_id"],
            ["paperdocumentdrafts.tenant_id", "paperdocumentdrafts.id"],
            name="fk_paperdraftversion_tenant",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("version_number >= 1", name="ck_paperdraftversion_number"),
        sa.CheckConstraint(
            "(status = 'draft' AND reviewed_by IS NULL AND reviewed_at IS NULL) OR (status = 'reviewed' AND reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL)",
            name="ck_paperdraftversion_review",
        ),
    )


def downgrade() -> None:
    """Drop only the independent document review tables."""
    op.drop_table("paperdocumentdraftversions")
    op.drop_index("ix_paperdocumentdrafts_tenant_id", table_name="paperdocumentdrafts")
    op.drop_table("paperdocumentdrafts")
