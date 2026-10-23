"""Tenant-owned optimistic concurrency boundary for document match requirements."""

from sqlalchemy import CheckConstraint, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


class PaperFieldPolicy(Base):
    """Latest revision pointer; immutable policy contents live in version rows."""

    __tablename__ = "paperfieldpolicies"
    __table_args__ = (CheckConstraint("latest_revision >= 1", name="ck_paperfieldpolicy_latest"),)

    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True
    )
    latest_revision: Mapped[int] = mapped_column(Integer, nullable=False)
