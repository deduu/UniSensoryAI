"""Immutable source fields, evidence, diagnostics, and review attestation."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKeyConstraint, String, Text, event
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Mapped, Mapper, mapped_column

from src.db.base import Base


class PaperDocumentDraftVersion(Base):
    """One immutable, tenant-qualified source review snapshot."""

    __tablename__ = "paperdocumentdraftversions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "draft_id"],
            ["paperdocumentdrafts.tenant_id", "paperdocumentdrafts.id"],
            name="fk_paperdraftversion_tenant",
            ondelete="CASCADE",
        ),
        CheckConstraint("version_number >= 1", name="ck_paperdraftversion_number"),
        CheckConstraint(
            "(status = 'draft' AND reviewed_by IS NULL AND reviewed_at IS NULL) OR (status = 'reviewed' AND reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL)",
            name="ck_paperdraftversion_review",
        ),
    )

    tenant_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    draft_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    version_number: Mapped[int] = mapped_column(primary_key=True)
    document: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    search_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    reviewed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


@event.listens_for(PaperDocumentDraftVersion, "before_update")
def _reject_update(
    _: Mapper[PaperDocumentDraftVersion], __: Connection, ___: PaperDocumentDraftVersion
) -> None:
    raise ValueError("Document draft versions are immutable")
