"""Atomic, durable ownership of tenant-qualified invoice duplicate keys."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, ForeignKeyConstraint, String, event
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Mapped, Mapper, mapped_column

from src.db.base import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class InvoiceDuplicateClaim(Base):
    """Retained SHA-256 business-key ownership, scoped to a tenant."""

    __tablename__ = "paperinvoiceduplicateclaims"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["paperinvoicecases.tenant_id", "paperinvoicecases.id"],
            name="fk_paperduplicate_case_tenant",
            ondelete="CASCADE",
        ),
        CheckConstraint("length(duplicate_key) = 64", name="ck_paperduplicate_key_length"),
    )

    tenant_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    duplicate_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    case_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, nullable=False
    )


@event.listens_for(InvoiceDuplicateClaim, "before_update")
def _reject_update(
    _: Mapper[InvoiceDuplicateClaim], __: Connection, ___: InvoiceDuplicateClaim
) -> None:
    raise ValueError("Invoice duplicate claims are immutable")
