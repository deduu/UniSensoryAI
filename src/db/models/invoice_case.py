"""Tenant-owned PAPER invoice case identity and concurrency boundary."""

from __future__ import annotations

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


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class InvoiceCase(Base):
    """Stable tenant and business identity with a mutable latest revision."""

    __tablename__ = "paperinvoicecases"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_paperinvoicecase_tenant_id"),
        CheckConstraint("latest_version >= 1", name="ck_paperinvoicecase_latest_version"),
    )

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    vendor_id: Mapped[str] = mapped_column(String(255), nullable=False)
    store_id: Mapped[str] = mapped_column(String(255), nullable=False)
    contract_number: Mapped[str] = mapped_column(String(255), nullable=False)
    latest_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, nullable=False
    )


@event.listens_for(InvoiceCase, "before_update")
def _reject_identity_update(_: Mapper[InvoiceCase], __: Connection, target: InvoiceCase) -> None:
    identity_fields = ("id", "tenant_id", "vendor_id", "store_id", "contract_number", "created_at")
    state = inspect(target)
    if any(state.attrs[field].history.has_changes() for field in identity_fields):
        raise ValueError("Invoice case identities are immutable")
