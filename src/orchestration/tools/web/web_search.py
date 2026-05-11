"""``WebSearchTool`` — the public ``Tool`` wrapping a pluggable search provider.

The tool is what chat agents (and OpenAI function-calling) actually invoke.
It owns:

- a ``SearchProvider`` (DuckDuckGo, Brave, ...) picked at construction;
- an optional ``CircuitBreaker`` so provider outages stop hammering the
  upstream API (and stop blocking the chat path).

Provider exceptions are caught and surfaced as ``ToolResult(success=False)``
so the LLM tool-call loop can keep running.
"""

from __future__ import annotations

import time
from typing import Any

from src.orchestration.interfaces.tool import Tool
from src.orchestration.middleware.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpen,
)
from src.orchestration.models.context import ToolInput
from src.orchestration.models.results import ToolResult
from src.orchestration.tools.web.providers.base import SearchProvider

_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "Free-text search query.",
        },
        "max_results": {
            "type": "integer",
            "description": "Maximum number of results to return.",
            "minimum": 1,
            "maximum": 20,
            "default": 5,
        },
    },
    "required": ["query"],
}


class WebSearchTool(Tool):
    """Tool exposing a ``SearchProvider`` to agents / function-calling LLMs.

    Args:
        provider: Concrete ``SearchProvider`` to delegate to.
        circuit_breaker: Optional breaker wrapping each provider call.
            Repeated provider failures stop the tool from calling the
            backend until the cooldown elapses.
        default_max_results: Fallback when the caller omits ``max_results``.
    """

    def __init__(
        self,
        *,
        provider: SearchProvider,
        circuit_breaker: CircuitBreaker | None = None,
        default_max_results: int = 5,
    ) -> None:
        self._provider = provider
        self._breaker = circuit_breaker
        self._default_max_results = default_max_results

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return (
            "Search the public web for recent or factual information. "
            "Returns a ranked list of results with title, url, and snippet."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return _INPUT_SCHEMA

    async def execute(self, tool_input: ToolInput) -> ToolResult:
        started = time.monotonic()
        query = tool_input.parameters.get("query")
        if not isinstance(query, str) or not query.strip():
            return ToolResult(
                tool_name=self.name,
                output=None,
                success=False,
                error="Missing required parameter: query",
                duration_ms=(time.monotonic() - started) * 1000,
                metadata={"provider": self._provider.name},
            )

        max_results = int(
            tool_input.parameters.get("max_results", self._default_max_results)
        )

        try:
            if self._breaker is not None:
                results = await self._breaker.call(
                    lambda: self._provider.search(query, max_results=max_results)
                )
            else:
                results = await self._provider.search(query, max_results=max_results)
        except CircuitBreakerOpen as exc:
            return ToolResult(
                tool_name=self.name,
                output=None,
                success=False,
                error=f"Web search unavailable: {exc}",
                duration_ms=(time.monotonic() - started) * 1000,
                metadata={
                    "provider": self._provider.name,
                    "error_type": "CircuitBreakerOpen",
                },
            )
        except Exception as exc:  # noqa: BLE001 — surface as soft failure
            return ToolResult(
                tool_name=self.name,
                output=None,
                success=False,
                error=str(exc),
                duration_ms=(time.monotonic() - started) * 1000,
                metadata={
                    "provider": self._provider.name,
                    "error_type": exc.__class__.__name__,
                },
            )

        return ToolResult(
            tool_name=self.name,
            output=[r.model_dump() for r in results],
            success=True,
            duration_ms=(time.monotonic() - started) * 1000,
            metadata={
                "provider": self._provider.name,
                "result_count": len(results),
            },
        )
