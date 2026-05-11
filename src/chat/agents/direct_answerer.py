"""LLM-only chat agent for direct (non-search) turns."""

from __future__ import annotations

from typing import Any

from src.orchestration.interfaces.agent import Agent
from src.orchestration.llm.base import LLMMessage, LLMProvider
from src.orchestration.models.context import AgentContext
from src.orchestration.models.results import AgentResult

_SYSTEM_PROMPT = (
    "You are a helpful assistant for the UniSensoryAI application. "
    "Answer the user's question concisely and accurately using only your "
    "own knowledge. If a question genuinely requires up-to-date or "
    "obscure information, say so plainly rather than guessing."
)


class DirectAnswererAgent(Agent):
    """Answer with the LLM alone, threading conversation history."""

    def __init__(
        self,
        *,
        llm: LLMProvider,
        temperature: float = 0.7,
        system_prompt: str = _SYSTEM_PROMPT,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> None:
        self._llm = llm
        self._temperature = temperature
        self._system_prompt = system_prompt
        self._tools = tools
        self._tool_choice = tool_choice

    @property
    def name(self) -> str:
        return "direct_answerer"

    @property
    def description(self) -> str:
        return "Answer the user directly from model knowledge."

    async def run(self, context: AgentContext) -> AgentResult:
        messages: list[LLMMessage] = [LLMMessage(role="system", content=self._system_prompt)]
        for turn in context.conversation_history:
            role = turn.get("role")
            content = turn.get("content") or ""
            if role in {"system", "user", "assistant", "tool"} and content:
                messages.append(LLMMessage(role=role, content=content))  # type: ignore[arg-type]
        messages.append(LLMMessage(role="user", content=context.user_message))

        response = await self._llm.complete(
            messages,
            temperature=self._temperature,
            tools=self._tools,
            tool_choice=self._tool_choice,
        )
        return AgentResult(
            agent_name=self.name,
            response=response.content,
            metadata={"finish_reason": response.finish_reason or ""},
            token_usage=response.token_usage,
        )
