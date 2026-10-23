"""Tenant-owned identity and optimistic concurrency boundary for source drafts."""

from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    event,
    inspect,
)
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Mapped, Mapper, mapped_column

from src.db.base import Base


class PaperDocumentDraft(Base):
    """Stable document role with an append-only sequence of source snapshots."""

    __tablename__ = "paperdocumentdrafts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_paperdraft_tenant_id"),
        CheckConstraint("latest_version >= 1", name="ck_paperdraft_latest"),
        CheckConstraint(
            "role IN ('rent_invoice','tax_invoice','utility_statement','supporting_document')",
            name="ck_paperdraft_role",
        ),
    )

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(40), nullable=False)
    latest_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )


@event.listens_for(PaperDocumentDraft, "before_update")
def _reject_identity_update(
    _: Mapper[PaperDocumentDraft], __: Connection, target: PaperDocumentDraft
) -> None:
    if any(
        inspect(target).attrs[field].history.has_changes()
        for field in ("id", "tenant_id", "role", "created_at")
    ):
        raise ValueError("Document draft identities are immutable")
