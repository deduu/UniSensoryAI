import enum
from sqlalchemy import String, DateTime, Text, JSON, ForeignKey, Integer, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from ..base import Base, utc_now
from typing import Optional, Any


class MessageRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatConversation(Base):
    """A chat conversation/session."""

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="New conversation")
    model_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    temperature: Mapped[Optional[float]] = mapped_column(Float, nullable=True, default=0.7)
    thinking_enabled: Mapped[bool] = mapped_column(default=False, nullable=False)
    streaming_enabled: Mapped[bool] = mapped_column(default=True, nullable=False)

    # JSON array of document IDs selected for grounding
    grounded_document_ids: Mapped[Optional[list[str]]] = mapped_column(JSON, nullable=True)

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

    # Relationships
    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )

    def __repr__(self) -> str:
        return f"<ChatConversation(id={self.id}, title={self.title})>"


class ChatMessage(Base):
    """A single message within a chat conversation."""

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("chatconversations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    role: Mapped[MessageRole] = mapped_column(
        String(20),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Optional thinking/reasoning content (for thinking mode)
    thinking_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Response metrics (only for assistant messages)
    prompt_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    model_used: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Citations as JSON array: [{doc_id, filename, excerpt}, ...]
    citations: Mapped[Optional[list[dict[str, Any]]]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )

    # Relationships
    conversation: Mapped["ChatConversation"] = relationship(back_populates="messages")

    def __repr__(self) -> str:
        return f"<ChatMessage(id={self.id}, role={self.role}, conversation_id={self.conversation_id})>"
