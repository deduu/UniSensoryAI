import enum
from sqlalchemy import String, DateTime, Enum, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from ..base import Base, utc_now
from typing import Optional, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .document import Document

class IngestionStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class IngestionJob(Base):
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    status: Mapped[IngestionStatus] = mapped_column(
        Enum(IngestionStatus, native_enum=False), # native_enum=False for wider compatibility
        default=IngestionStatus.PENDING,
        nullable=False,
        index=True
    )
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )
    
    # Store arbitrary metadata (e.g. file size, original filename, error details)
    meta: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Relationships
    documents: Mapped[list["Document"]] = relationship(back_populates="ingestion_job", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<IngestionJob(id={self.id}, status={self.status}, file_path={self.file_path})>"
