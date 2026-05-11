"""Result types returned by tools and agents."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ToolCallRecord(BaseModel):
    """Audit record of a single tool invocation made by an agent.

    Attached to ``AgentResult.tool_calls`` so callers (and stored
    transcripts) can reconstruct which tools fired and with what arguments.
    """

    tool_name: str
    input_params: dict[str, Any]
    output: Any
    duration_ms: float
    success: bool


class ToolResult(BaseModel):
    """Outcome of ``Tool.execute``.

    Attributes:
        tool_name: Echoed from the invoking ``ToolInput`` for convenience.
        output: Arbitrary tool-specific payload.
        success: ``False`` indicates a handled failure; an exception inside
            ``execute`` should still raise, not return ``success=False``.
        error: Human-readable explanation when ``success`` is False.
        duration_ms: Wall-clock execution time recorded by the tool.
        metadata: Optional bag for provider-specific details
            (e.g. raw response headers, fallback notes).
    """

    tool_name: str
    output: Any
    success: bool = True
    error: str | None = None
    duration_ms: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentResult(BaseModel):
    """Outcome of ``Agent.run``.

    Attributes:
        request_id: Correlation id; defaults to a fresh UUID.
        agent_name: Identifier of the agent that produced the result.
        response: User-visible response text.
        tool_calls: Audit trail of tool invocations during this run.
        metadata: Free-form bag (sources, query_type, refined_queries, ...).
        token_usage: Token accounting from the LLM provider, when known.
        duration_ms: Wall-clock runtime of the agent.
        created_at: Timestamp when the result was assembled.
    """

    request_id: UUID = Field(default_factory=uuid4)
    agent_name: str
    response: str
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    token_usage: dict[str, int] = Field(default_factory=dict)
    duration_ms: float = 0.0
    created_at: datetime = Field(default_factory=_utcnow)
