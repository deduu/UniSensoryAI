"""Append-only audit history for document matching field requirements."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, String, event
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Mapped, Mapper, mapped_column

from src.db.base import Base


class PaperFieldPolicyVersion(Base):
    """One tenant-qualified immutable requirement policy revision."""

    __tablename__ = "paperfieldpolicyversions"
    __table_args__ = (CheckConstraint("revision >= 1", name="ck_paperfieldpolicyversion_revision"),)

    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("paperfieldpolicies.tenant_id", ondelete="CASCADE"), primary_key=True
    )
    revision: Mapped[int] = mapped_column(primary_key=True)
    requirements: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    updated_by: Mapped[str] = mapped_column(String(128), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


@event.listens_for(PaperFieldPolicyVersion, "before_update")
def _reject_update(
    _: Mapper[PaperFieldPolicyVersion], __: Connection, ___: PaperFieldPolicyVersion
) -> None:
    raise ValueError("Matching policy versions are immutable")
