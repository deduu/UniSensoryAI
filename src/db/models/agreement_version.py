"""Immutable agreement term snapshots with explicit effective intervals."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import JSON, CheckConstraint, Date, DateTime, ForeignKeyConstraint, String, event
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Mapped, Mapper, mapped_column

from src.db.base import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AgreementVersion(Base):
    """One immutable draft payload, linked to its tenant and agreement."""

    __tablename__ = "paperagreementversions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "agreement_id"],
            ["paperagreements.tenant_id", "paperagreements.id"],
            name="fk_paperversion_agreement_tenant",
            ondelete="CASCADE",
        ),
        CheckConstraint("version_number >= 1", name="ck_paperversion_number"),
        CheckConstraint("effective_to >= effective_from", name="ck_paperversion_effective_dates"),
    )

    tenant_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    agreement_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    version_number: Mapped[int] = mapped_column(primary_key=True)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date] = mapped_column(Date, nullable=False)
    draft: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, nullable=False
    )


@event.listens_for(AgreementVersion, "before_update")
def _reject_update(_: Mapper[AgreementVersion], __: Connection, ___: AgreementVersion) -> None:
    raise ValueError("Agreement versions are immutable")
