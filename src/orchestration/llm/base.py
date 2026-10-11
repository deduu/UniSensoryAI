"""LLM provider contract."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

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

    @field_validator("token_usage", mode="before")
    @classmethod
    def _drop_non_int_usage(cls, value: Any) -> Any:
        # Providers (OpenAI, OpenRouter, etc.) increasingly return nested
        # objects under `usage` such as `prompt_tokens_details`,
        # `completion_tokens_details`, and `latency_checkpoint`. The full
        # payload is preserved on `raw`; here we keep only the scalar int
        # counters so downstream aggregation stays well-typed.
        if not isinstance(value, dict):
            return value
        return {k: v for k, v in value.items() if isinstance(v, int) and not isinstance(v, bool)}


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
