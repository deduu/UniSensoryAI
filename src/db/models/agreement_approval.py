"""Separate immutable approval snapshots for reviewed agreement versions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKeyConstraint, String, event
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Mapped, Mapper, mapped_column

from src.db.base import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AgreementApproval(Base):
    """An authoritative approval, unique for a tenant/agreement/version."""

    __tablename__ = "paperagreementapprovals"
    __table_args__ = (
        ForeignKeyConstraint(
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

    tenant_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    agreement_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    version_number: Mapped[int] = mapped_column(primary_key=True)
    decision: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    approved_by: Mapped[str] = mapped_column(String(255), nullable=False)
    approved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, nullable=False
    )


@event.listens_for(AgreementApproval, "before_update")
def _reject_update(_: Mapper[AgreementApproval], __: Connection, ___: AgreementApproval) -> None:
    raise ValueError("Agreement approvals are immutable")
