"""Add isolated PAPER agreement identities, snapshots, and approvals.

Revision ID: 8b3e1c725f60
Revises: 5ac699391b63
Create Date: 2026-10-14
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "8b3e1c725f60"
down_revision: str | Sequence[str] | None = "5ac699391b63"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create additive tenant-scoped agreement master tables."""
    op.create_table(
        "paperagreements",
        sa.Column("id", sa.String(50), nullable=False),
        sa.Column("tenant_id", sa.String(50), nullable=False),
        sa.Column("vendor_id", sa.String(255), nullable=False),
        sa.Column("store_id", sa.String(255), nullable=False),
        sa.Column("contract_number", sa.String(255), nullable=False),
        sa.Column("latest_version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_paperagreement_tenant_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "vendor_id",
            "store_id",
            "contract_number",
            name="uq_paperagreement_identity",
        ),
        sa.CheckConstraint("latest_version >= 1", name="ck_paperagreement_latest_version"),
    )
    op.create_index("ix_paperagreements_tenant_id", "paperagreements", ["tenant_id"])
    op.create_table(
        "paperagreementversions",
        sa.Column("tenant_id", sa.String(50), nullable=False),
        sa.Column("agreement_id", sa.String(50), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=False),
        sa.Column("draft", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("tenant_id", "agreement_id", "version_number"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "agreement_id"],
            ["paperagreements.tenant_id", "paperagreements.id"],
            name="fk_paperversion_agreement_tenant",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("version_number >= 1", name="ck_paperversion_number"),
        sa.CheckConstraint(
            "effective_to >= effective_from", name="ck_paperversion_effective_dates"
        ),
    )
    op.create_table(
        "paperagreementapprovals",
        sa.Column("tenant_id", sa.String(50), nullable=False),
        sa.Column("agreement_id", sa.String(50), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("decision", sa.JSON(), nullable=False),
        sa.Column("approved_by", sa.String(255), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("tenant_id", "agreement_id", "version_number"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "agreement_id", "version_number"],
            [
                "paperagreementversions.tenant_id",
                "paperagreementversions.agreement_id",
                "paperagreementversions.version_number",
            ],
            name="fk_paperapproval_version_tenant",
            ondelete="CASCADE",
        ),
    )


def downgrade() -> None:
    """Remove only PAPER tables, leaving existing workflows unchanged."""
    op.drop_table("paperagreementapprovals")
    op.drop_table("paperagreementversions")
    op.drop_index("ix_paperagreements_tenant_id", table_name="paperagreements")
    op.drop_table("paperagreements")
