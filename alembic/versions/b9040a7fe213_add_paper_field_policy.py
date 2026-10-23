"""Add tenant-scoped immutable document matching field policy history.

Revision ID: b9040a7fe213
Revises: a1090c3d67ef
Create Date: 2026-10-20
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b9040a7fe213"
down_revision: str | Sequence[str] | None = "a1090c3d67ef"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add revision heads and immutable tenant policy snapshots."""
    op.create_table(
        "paperfieldpolicies",
        sa.Column("tenant_id", sa.String(50), nullable=False),
        sa.Column("latest_revision", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("tenant_id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.CheckConstraint("latest_revision >= 1", name="ck_paperfieldpolicy_latest"),
    )
    op.create_table(
        "paperfieldpolicyversions",
        sa.Column("tenant_id", sa.String(50), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("requirements", sa.JSON(), nullable=False),
        sa.Column("updated_by", sa.String(128), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("tenant_id", "revision"),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["paperfieldpolicies.tenant_id"], ondelete="CASCADE"
        ),
        sa.CheckConstraint("revision >= 1", name="ck_paperfieldpolicyversion_revision"),
    )


def downgrade() -> None:
    """Remove only the document matching requirement policy tables."""
    op.drop_table("paperfieldpolicyversions")
    op.drop_table("paperfieldpolicies")
