"""Chat service for managing conversations and messages."""

from typing import Optional, Sequence, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload
import uuid

from src.db.models.chat import ChatConversation, ChatMessage, MessageRole
from .base import BaseService


class ChatService(BaseService[ChatConversation]):
    """Service for chat conversation and message operations."""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, ChatConversation)

    async def create_conversation(
        self,
        title: str = "New conversation",
        model_id: Optional[str] = None,
        temperature: float = 0.7,
        thinking_enabled: bool = False,
        streaming_enabled: bool = True,
        grounded_document_ids: Optional[list[str]] = None,
        *,
        tenant_id: str,
    ) -> ChatConversation:
        """Create a new chat conversation."""
        conv = ChatConversation(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            title=title,
            model_id=model_id,
            temperature=temperature,
            thinking_enabled=thinking_enabled,
            streaming_enabled=streaming_enabled,
            grounded_document_ids=grounded_document_ids,
        )
        self.db.add(conv)
        await self.db.flush()
        await self.db.refresh(conv)
        return conv

    async def list_conversations(
        self,
        limit: int = 50,
        offset: int = 0,
        *,
        tenant_id: Optional[str] = None,
    ) -> Sequence[ChatConversation]:
        """List conversations ordered by most recently updated."""
        stmt = (
            select(ChatConversation)
            .order_by(desc(ChatConversation.updated_at))
            .limit(limit)
            .offset(offset)
        )
        if tenant_id is not None:
            stmt = stmt.where(ChatConversation.tenant_id == tenant_id)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_conversation_with_messages(
        self,
        conversation_id: str,
        *,
        tenant_id: Optional[str] = None,
    ) -> Optional[ChatConversation]:
        """Get a conversation with all its messages eagerly loaded."""
        stmt = (
            select(ChatConversation)
            .options(selectinload(ChatConversation.messages))
            .where(ChatConversation.id == conversation_id)
        )
        if tenant_id is not None:
            stmt = stmt.where(ChatConversation.tenant_id == tenant_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def update_conversation(
        self, conversation_id: str, **data: Any
    ) -> ChatConversation:
        """Update conversation metadata."""
        return await self.update(conversation_id, **data)

    async def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation and all its messages (cascade)."""
        return await self.delete(conversation_id)

    async def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        thinking_content: Optional[str] = None,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
        total_tokens: Optional[int] = None,
        latency_ms: Optional[int] = None,
        model_used: Optional[str] = None,
        citations: Optional[list[dict[str, Any]]] = None,
    ) -> ChatMessage:
        """Add a message to a conversation."""
        msg = ChatMessage(
            id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            role=role,
            content=content,
            thinking_content=thinking_content,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            model_used=model_used,
            citations=citations,
        )
        self.db.add(msg)
        await self.db.flush()
        await self.db.refresh(msg)
        return msg

    async def get_messages(
        self, conversation_id: str
    ) -> Sequence[ChatMessage]:
        """Get all messages for a conversation, ordered by creation time."""
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.conversation_id == conversation_id)
            .order_by(ChatMessage.created_at)
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()
