"""LLM provider contract."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Literal

from pydantic import BaseModel, Field

LLMRole = Literal["system", "user", "assistant", "tool"]


class LLMMessage(BaseModel):
    """Single message in a chat-completion request.

    Attributes:
        role: One of ``system`` / ``user`` / ``assistant`` / ``tool``.
        content: Message body. Required for text turns; may be empty for
            assistant turns that only carry tool calls.
        name: Optional speaker label (used by some providers for multi-actor
            traces).
        tool_call_id: When ``role == "tool"``, identifies the tool call
            being answered.
    """

    role: LLMRole
    content: str = ""
    name: str | None = None
    tool_call_id: str | None = None


class LLMResponse(BaseModel):
    """Result of an LLM completion call."""

    content: str
    model: str
    finish_reason: str | None = None
    token_usage: dict[str, int] = Field(default_factory=dict)
    raw: dict[str, Any] = Field(default_factory=dict)


class LLMProvider(ABC):
    """Base class for LLM clients used by orchestration agents.

    Implementations are async and free of request-scoped state.
    """

    @abstractmethod
    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        response_format: dict[str, Any] | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> LLMResponse:
        """Run a single non-streaming completion."""
