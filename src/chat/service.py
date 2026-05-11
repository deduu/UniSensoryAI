"""High-level entry point for the chat orchestration pipeline."""

from __future__ import annotations

from typing import Any

from src.orchestration.interfaces.orchestrator import Orchestrator
from src.orchestration.models.context import AgentContext
from src.orchestration.models.results import AgentResult


class ChatOrchestrationService:
    """Thin facade the FastAPI endpoint calls into.

    Owns one ``Orchestrator``; converts request fields into an
    ``AgentContext`` and runs the pipeline. Streaming is wrapped at the
    endpoint layer — this service stays request-shape agnostic.
    """

    def __init__(self, orchestrator: Orchestrator) -> None:
        self._orchestrator = orchestrator

    async def run(
        self,
        *,
        user_message: str,
        conversation_history: list[dict[str, Any]] | None = None,
        tenant_id: str | None = None,
        user_id: str | None = None,
        session_id: str | None = None,
        timeout_seconds: float | None = None,
    ) -> AgentResult:
        context = AgentContext(
            user_message=user_message,
            conversation_history=conversation_history or [],
            tenant_id=tenant_id,
            user_id=user_id,
            session_id=session_id,
        )
        return await self._orchestrator.run(context, timeout_seconds=timeout_seconds)
