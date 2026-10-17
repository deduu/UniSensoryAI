"""Immutable AP decisions attached to exact PAPER case versions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKeyConstraint, String, event
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Mapped, Mapper, mapped_column

from src.db.base import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class InvoiceCaseDecision(Base):
    """An immutable review decision unique for each tenant/case/revision."""

    __tablename__ = "paperinvoicecasedecisions"
    __table_args__ = (
        ForeignKeyConstraint(
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

    tenant_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    case_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    version_number: Mapped[int] = mapped_column(primary_key=True)
    decision: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    decided_by: Mapped[str] = mapped_column(String(255), nullable=False)
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, nullable=False
    )


@event.listens_for(InvoiceCaseDecision, "before_update")
def _reject_update(
    _: Mapper[InvoiceCaseDecision], __: Connection, ___: InvoiceCaseDecision
) -> None:
    raise ValueError("Invoice case decisions are immutable")
