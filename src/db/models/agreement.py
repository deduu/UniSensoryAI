"""Tenant-owned agreement identities and the revision concurrency boundary."""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
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


class Agreement(Base):
    """Stable agreement identity; only the revision counter changes."""

    __tablename__ = "paperagreements"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_paperagreement_tenant_id"),
        UniqueConstraint(
            "tenant_id",
            "vendor_id",
            "store_id",
            "contract_number",
            name="uq_paperagreement_identity",
        ),
        CheckConstraint("latest_version >= 1", name="ck_paperagreement_latest_version"),
    )

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    vendor_id: Mapped[str] = mapped_column(String(255), nullable=False)
    store_id: Mapped[str] = mapped_column(String(255), nullable=False)
    contract_number: Mapped[str] = mapped_column(String(255), nullable=False)
    latest_version: Mapped[int] = mapped_column(Integer, nullable=False)


@event.listens_for(Agreement, "before_update")
def _reject_identity_update(_: Mapper[Agreement], __: Connection, target: Agreement) -> None:
    state = inspect(target)
    identity_fields = ("id", "tenant_id", "vendor_id", "store_id", "contract_number")
    if any(state.attrs[field].history.has_changes() for field in identity_fields):
        raise ValueError("Agreement identities are immutable")
