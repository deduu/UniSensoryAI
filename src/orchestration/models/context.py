"""Frozen input contexts flowing into tools and agents."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ToolInput(BaseModel):
    """Validated payload for a single tool invocation.

    Attributes:
        tool_name: Identifier of the tool being called. Must match the
            target tool's ``name`` property.
        parameters: Caller-supplied arguments. The receiving tool is
            responsible for schema-validating these against its
            ``input_schema``.
        request_id: Correlation id, auto-generated when omitted. Useful
            for tracing tool calls back to the originating agent run.
    """

    tool_name: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    request_id: UUID = Field(default_factory=uuid4)


class AgentContext(BaseModel):
    """Immutable context handed to every ``Agent.run`` call.

    Frozen on purpose: parallel strategies share the same context across
    agents, so accidental mutation would create non-deterministic bugs.
    Threads use ``model_copy(update=...)`` to derive a new context.

    Attributes:
        request_id: Correlation id for tracing one user turn end-to-end.
        user_message: The latest user input.
        conversation_history: Prior messages in OpenAI chat-completion shape
            (``{"role": ..., "content": ...}``).
        available_tools: Names of tools the agent is allowed to call.
        metadata: Free-form bag for strategy-specific state (e.g.,
            ``refined_queries`` threaded from the analyzer to the
            researcher).
        created_at: Timestamp the context was constructed.
        tenant_id: UniSensoryAI tenant, propagated for citation persistence
            and rate-limit accounting.
        user_id: Authenticated user, when available.
        session_id: Chat conversation id, when applicable.
    """

    request_id: UUID = Field(default_factory=uuid4)
    user_message: str
    conversation_history: list[dict[str, Any]] = Field(default_factory=list)
    available_tools: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_utcnow)

    tenant_id: str | None = None
    user_id: str | None = None
    session_id: str | None = None

    model_config = ConfigDict(frozen=True)
