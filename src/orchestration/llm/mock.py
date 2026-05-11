"""Deterministic ``LLMProvider`` for tests."""

from __future__ import annotations

from typing import Any

from src.orchestration.llm.base import LLMMessage, LLMProvider, LLMResponse


class MockLLMProvider(LLMProvider):
    """LLM stand-in that replays canned responses in order.

    Args:
        responses: List of strings; each ``complete`` call pops the next.
        model: Identifier echoed back in ``LLMResponse.model``.
    """

    def __init__(
        self,
        responses: list[str],
        *,
        model: str = "mock",
    ) -> None:
        self._responses = list(responses)
        self._model = model
        self.calls: list[list[LLMMessage]] = []
        self.last_kwargs: dict[str, Any] = {}

    @property
    def call_count(self) -> int:
        return len(self.calls)

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
        self.calls.append(messages)
        self.last_kwargs = {
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": response_format,
            "tools": tools,
            "tool_choice": tool_choice,
        }
        if not self._responses:
            raise IndexError("MockLLMProvider: no canned responses left")
        body = self._responses.pop(0)
        return LLMResponse(
            content=body,
            model=self._model,
            finish_reason="stop",
            token_usage={
                "prompt_tokens": sum(len(m.content) for m in messages),
                "completion_tokens": len(body),
            },
        )
