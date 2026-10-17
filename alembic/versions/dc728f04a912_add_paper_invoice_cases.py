"""Add isolated PAPER invoice cases, immutable reviews, and duplicate claims.

Revision ID: dc728f04a912
Revises: 8b3e1c725f60
Create Date: 2026-10-14
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "dc728f04a912"
down_revision: str | Sequence[str] | None = "8b3e1c725f60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create additive tenant-scoped invoice reconciliation case tables."""
    op.create_table(
        "paperinvoicecases",
        sa.Column("id", sa.String(50), nullable=False),
        sa.Column("tenant_id", sa.String(50), nullable=False),
        sa.Column("vendor_id", sa.String(255), nullable=False),
        sa.Column("store_id", sa.String(255), nullable=False),
        sa.Column("contract_number", sa.String(255), nullable=False),
        sa.Column("latest_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_paperinvoicecase_tenant_id"),
        sa.CheckConstraint("latest_version >= 1", name="ck_paperinvoicecase_latest_version"),
    )
    op.create_index("ix_paperinvoicecases_tenant_id", "paperinvoicecases", ["tenant_id"])
    op.create_table(
        "paperinvoicecaseversions",
        sa.Column("tenant_id", sa.String(50), nullable=False),
        sa.Column("case_id", sa.String(50), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("package", sa.JSON(), nullable=False),
        sa.Column("assessment", sa.JSON(), nullable=False),
        sa.Column("duplicate_of", sa.String(50), nullable=True),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("tenant_id", "case_id", "version_number"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["paperinvoicecases.tenant_id", "paperinvoicecases.id"],
            name="fk_papercaseversion_case_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "duplicate_of"],
            ["paperinvoicecases.tenant_id", "paperinvoicecases.id"],
            name="fk_papercaseversion_duplicate_tenant",
        ),
        sa.CheckConstraint("version_number >= 1", name="ck_papercaseversion_number"),
        sa.CheckConstraint(
            "duplicate_of IS NULL OR duplicate_of <> case_id",
            name="ck_papercaseversion_duplicate_other",
        ),
    )
    op.create_table(
        "paperinvoicecasedecisions",
        sa.Column("tenant_id", sa.String(50), nullable=False),
        sa.Column("case_id", sa.String(50), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("decision", sa.JSON(), nullable=False),
        sa.Column("decided_by", sa.String(255), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("tenant_id", "case_id", "version_number"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id", "version_number"],
            [
                "paperinvoicecaseversions.tenant_id",
                "paperinvoicecaseversions.case_id",
                "paperinvoicecaseversions.version_number",
            ],
            name="fk_papercasedecision_version_tenant",
            ondelete="CASCADE",
        ),
    )
    op.create_table(
        "paperinvoiceduplicateclaims",
        sa.Column("tenant_id", sa.String(50), nullable=False),
        sa.Column("duplicate_key", sa.String(64), nullable=False),
        sa.Column("case_id", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("tenant_id", "duplicate_key"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["paperinvoicecases.tenant_id", "paperinvoicecases.id"],
            name="fk_paperduplicate_case_tenant",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("length(duplicate_key) = 64", name="ck_paperduplicate_key_length"),
    )
    op.create_index(
        "ix_paperinvoiceduplicateclaims_case_id", "paperinvoiceduplicateclaims", ["case_id"]
    )


def downgrade() -> None:
    """Remove invoice case tables while preserving agreement and prior workflows."""
    op.drop_index(
        "ix_paperinvoiceduplicateclaims_case_id", table_name="paperinvoiceduplicateclaims"
    )
    op.drop_table("paperinvoiceduplicateclaims")
    op.drop_table("paperinvoicecasedecisions")
    op.drop_table("paperinvoicecaseversions")
    op.drop_index("ix_paperinvoicecases_tenant_id", table_name="paperinvoicecases")
    op.drop_table("paperinvoicecases")
