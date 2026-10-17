"""Immutable PAPER invoice package and assessment snapshots."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKeyConstraint, String, event
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Mapped, Mapper, mapped_column

from src.db.base import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class InvoiceCaseVersion(Base):
    """One tenant-qualified immutable case revision."""

    __tablename__ = "paperinvoicecaseversions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["paperinvoicecases.tenant_id", "paperinvoicecases.id"],
            name="fk_papercaseversion_case_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "duplicate_of"],
            ["paperinvoicecases.tenant_id", "paperinvoicecases.id"],
            name="fk_papercaseversion_duplicate_tenant",
        ),
        CheckConstraint("version_number >= 1", name="ck_papercaseversion_number"),
        CheckConstraint(
            "duplicate_of IS NULL OR duplicate_of <> case_id",
            name="ck_papercaseversion_duplicate_other",
        ),
    )

    tenant_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    case_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    version_number: Mapped[int] = mapped_column(primary_key=True)
    package: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    assessment: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    duplicate_of: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, nullable=False
    )


@event.listens_for(InvoiceCaseVersion, "before_update")
def _reject_update(_: Mapper[InvoiceCaseVersion], __: Connection, ___: InvoiceCaseVersion) -> None:
    raise ValueError("Invoice case versions are immutable")
