"""Tests for ``WebSearchTool`` — the public Tool wrapping a SearchProvider."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from src.orchestration.middleware.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpen,
)
from src.orchestration.models.context import ToolInput
from src.orchestration.tools.web.models import WebSearchResult
from src.orchestration.tools.web.providers.base import SearchProvider
from src.orchestration.tools.web.web_search import WebSearchTool


class _StubProvider(SearchProvider):
    """In-memory provider that records calls and optionally fails."""

    def __init__(
        self,
        results: list[WebSearchResult] | None = None,
        *,
        fail_n_times: int = 0,
    ) -> None:
        self._results = results or []
        self._fail_remaining = fail_n_times
        self.call_count = 0
        self.queries: list[str] = []

    @property
    def name(self) -> str:
        return "stub"

    async def search(
        self,
        query: str,
        *,
        max_results: int = 5,
    ) -> list[WebSearchResult]:
        self.call_count += 1
        self.queries.append(query)
        if self._fail_remaining > 0:
            self._fail_remaining -= 1
            raise RuntimeError("provider boom")
        return self._results[:max_results]


def _result(url: str, *, title: str = "T") -> WebSearchResult:
    return WebSearchResult(title=title, url=url, snippet="snip", provider="stub")


def test_web_search_tool_metadata() -> None:
    tool = WebSearchTool(provider=_StubProvider())
    assert tool.name == "web_search"
    assert "search" in tool.description.lower()
    schema: dict[str, Any] = tool.input_schema
    assert schema["type"] == "object"
    assert "query" in schema["properties"]
    assert "query" in schema["required"]


@pytest.mark.asyncio
async def test_web_search_tool_calls_provider_and_packs_result() -> None:
    provider = _StubProvider([_result("https://a.example"), _result("https://b.example")])
    tool = WebSearchTool(provider=provider)

    result = await tool.execute(
        ToolInput(tool_name="web_search", parameters={"query": "python", "max_results": 2}),
    )

    assert result.success is True
    assert result.tool_name == "web_search"
    assert provider.queries == ["python"]
    # Output is a serialisable list of dicts so it can flow into LLM tool results.
    assert isinstance(result.output, list)
    assert result.output[0]["url"] == "https://a.example"
    assert result.metadata["provider"] == "stub"
    assert result.metadata["result_count"] == 2


@pytest.mark.asyncio
async def test_web_search_tool_validates_missing_query() -> None:
    tool = WebSearchTool(provider=_StubProvider())
    result = await tool.execute(ToolInput(tool_name="web_search", parameters={}))
    assert result.success is False
    assert "query" in (result.error or "")


@pytest.mark.asyncio
async def test_web_search_tool_wraps_provider_errors_as_failure() -> None:
    tool = WebSearchTool(provider=_StubProvider(fail_n_times=1))
    result = await tool.execute(
        ToolInput(tool_name="web_search", parameters={"query": "x"}),
    )
    assert result.success is False
    assert "boom" in (result.error or "")


@pytest.mark.asyncio
async def test_web_search_tool_uses_circuit_breaker() -> None:
    """Repeated provider failures must trip the breaker and fast-fail."""
    breaker = CircuitBreaker(failure_threshold=2, recovery_seconds=60.0)
    provider = _StubProvider(fail_n_times=99)
    tool = WebSearchTool(provider=provider, circuit_breaker=breaker)

    # Two real failures should trip the breaker.
    for _ in range(2):
        result = await tool.execute(
            ToolInput(tool_name="web_search", parameters={"query": "q"}),
        )
        assert result.success is False

    # Third call: provider must NOT be called; tool surfaces breaker-open.
    before = provider.call_count
    result = await tool.execute(
        ToolInput(tool_name="web_search", parameters={"query": "q"}),
    )
    assert provider.call_count == before  # provider untouched
    assert result.success is False
    assert "circuit" in (result.error or "").lower()
    assert isinstance(result.metadata.get("error_type"), str)
    assert "CircuitBreakerOpen" in result.metadata["error_type"]


@pytest.mark.asyncio
async def test_web_search_tool_records_duration() -> None:
    provider = _StubProvider([_result("https://x.example")])
    tool = WebSearchTool(provider=provider)
    result = await tool.execute(
        ToolInput(tool_name="web_search", parameters={"query": "q"}),
    )
    assert result.duration_ms >= 0.0


@pytest.mark.asyncio
async def test_web_search_tool_concurrent_calls_share_breaker() -> None:
    """Smoke test: concurrent calls don't corrupt the breaker counter."""
    breaker = CircuitBreaker(failure_threshold=10, recovery_seconds=60.0)
    provider = _StubProvider([_result("https://a.example")])
    tool = WebSearchTool(provider=provider, circuit_breaker=breaker)

    calls = [
        tool.execute(ToolInput(tool_name="web_search", parameters={"query": str(i)}))
        for i in range(5)
    ]
    results = await asyncio.gather(*calls)
    assert all(r.success for r in results)
    assert provider.call_count == 5
