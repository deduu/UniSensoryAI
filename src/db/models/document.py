from sqlalchemy import String, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from ..base import Base, utc_now
from typing import Optional, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .ingestion import IngestionJob

class Document(Base):
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_id: Mapped[Optional[str]] = mapped_column(ForeignKey("ingestionjobs.id", ondelete="SET NULL"), index=True, nullable=True)
    
    filename: Mapped[str] = mapped_column(String, nullable=False)
    content_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True) # Full extracted text
    content_chunks: Mapped[Optional[list[dict[str, Any]]]] = mapped_column(JSON, nullable=True) # Structured chunks
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
    
    # Relationships
    ingestion_job: Mapped[Optional["IngestionJob"]] = relationship(back_populates="documents")

    def __repr__(self) -> str:
        return f"<Document(id={self.id}, filename={self.filename})>"
