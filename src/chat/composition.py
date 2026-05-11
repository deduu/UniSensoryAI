"""Composition root for the chat application.

``build_chat_orchestrator`` is the single place where all dependencies
(LLM client, search provider, content fetcher, circuit breaker, agents)
are wired together. Callers — the FastAPI endpoint or tests — pass in a
``ChatSettings`` instance and optional dependency overrides.

The function deliberately accepts pre-built collaborators so tests can
inject ``MockLLMProvider`` and stub tools without monkey-patching. The
production endpoint omits the overrides and lets composition build the
real OpenAI-compatible client + DuckDuckGo/Brave provider.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Protocol

from src.chat.agents.chat_pipeline import ChatPipelineAgent
from src.chat.agents.direct_answerer import DirectAnswererAgent
from src.chat.agents.query_analyzer import QueryAnalyzerAgent
from src.chat.agents.synthesizer import SynthesizerAgent
from src.chat.agents.web_researcher import WebResearcherAgent
from src.orchestration.interfaces.orchestrator import Orchestrator
from src.orchestration.llm.base import LLMProvider
from src.orchestration.llm.openai_compat import OpenAICompatibleClient
from src.orchestration.middleware.circuit_breaker import CircuitBreaker
from src.orchestration.models.context import ToolInput
from src.orchestration.models.results import ToolResult
from src.orchestration.strategies.single_agent import SingleAgentStrategy
from src.orchestration.tools.web.content_fetcher import ContentFetcher
from src.orchestration.tools.web.providers.brave import BraveSearchProvider
from src.orchestration.tools.web.providers.duckduckgo import (
    DuckDuckGoSearchProvider,
)
from src.orchestration.tools.web.web_search import WebSearchTool


class _SearchToolLike(Protocol):
    name: str

    async def execute(self, tool_input: ToolInput) -> ToolResult:
        ...


class _ContentFetcherLike(Protocol):
    async def fetch(self, url: str, *, max_chars: int = 20000) -> str:
        ...


@dataclass(frozen=True)
class ChatSettings:
    """Knobs for the chat pipeline.

    Attributes:
        api_key: OpenAI-compatible API key.
        api_base: Base URL of the chat-completions API.
        model: Model identifier.
        search_provider: ``"duckduckgo"`` or ``"brave"``.
        brave_api_key: Required when ``search_provider == "brave"``.
        max_search_results: Per-query cap passed to the search tool.
        max_research_pages: Cap on pages fetched across all refined queries.
        timeout_seconds: Outer orchestrator timeout for the whole turn.
    """

    api_key: str
    api_base: str
    model: str
    search_provider: str = "duckduckgo"
    brave_api_key: str | None = None
    max_search_results: int = 5
    max_research_pages: int = 4
    timeout_seconds: float = 30.0

    @classmethod
    def from_env(
        cls,
        *,
        api_key: str | None = None,
        api_base: str | None = None,
        model: str | None = None,
    ) -> "ChatSettings":
        """Build settings from environment variables with optional overrides."""
        return cls(
            api_key=api_key or os.getenv("OPENAI_API_KEY", ""),
            api_base=(api_base or os.getenv("OPENAI_API_BASE") or "https://api.openai.com/v1").rstrip("/"),
            model=model or os.getenv("OPENAI_MODEL", "gpt-4o"),
            search_provider=os.getenv("WEB_SEARCH_PROVIDER", "duckduckgo").lower(),
            brave_api_key=os.getenv("BRAVE_API_KEY") or None,
            max_search_results=int(os.getenv("WEB_SEARCH_MAX_RESULTS", "5")),
            max_research_pages=int(os.getenv("WEB_RESEARCH_MAX_PAGES", "4")),
            timeout_seconds=float(os.getenv("CHAT_ORCHESTRATION_TIMEOUT", "30")),
        )


def build_chat_orchestrator(
    *,
    settings: ChatSettings,
    analyzer_llm: LLMProvider | None = None,
    answer_llm: LLMProvider | None = None,
    synthesizer_llm: LLMProvider | None = None,
    web_search_tool: _SearchToolLike | None = None,
    content_fetcher: _ContentFetcherLike | None = None,
) -> Orchestrator:
    """Wire all collaborators and return a ready-to-run ``Orchestrator``.

    Args:
        settings: Pipeline configuration.
        analyzer_llm: Override for the analyzer's LLM (tests). Defaults to
            a real OpenAI-compatible client.
        answer_llm: Override for the direct-answerer LLM.
        synthesizer_llm: Override for the synthesizer LLM.
        web_search_tool: Override the web-search tool. When omitted, builds
            a ``WebSearchTool`` from ``settings.search_provider`` wrapped in
            a 3-failure / 60s ``CircuitBreaker``.
        content_fetcher: Override the page-body fetcher.

    Returns:
        An ``Orchestrator`` running a ``SingleAgentStrategy`` over the
        composite ``ChatPipelineAgent``.
    """
    default_llm: LLMProvider | None = None
    if analyzer_llm is None or answer_llm is None or synthesizer_llm is None:
        default_llm = OpenAICompatibleClient(
            api_key=settings.api_key,
            base_url=settings.api_base,
            model=settings.model,
        )

    analyzer = QueryAnalyzerAgent(llm=analyzer_llm or default_llm)  # type: ignore[arg-type]
    direct = DirectAnswererAgent(llm=answer_llm or default_llm)  # type: ignore[arg-type]
    synth = SynthesizerAgent(llm=synthesizer_llm or default_llm)  # type: ignore[arg-type]

    if web_search_tool is None:
        web_search_tool = _build_default_web_search_tool(settings)
    if content_fetcher is None:
        content_fetcher = ContentFetcher()

    researcher = WebResearcherAgent(
        web_search=web_search_tool,
        content_fetcher=content_fetcher,
        max_pages=settings.max_research_pages,
        results_per_query=settings.max_search_results,
    )

    pipeline = ChatPipelineAgent(
        analyzer=analyzer,
        direct_answerer=direct,
        web_researcher=researcher,
        synthesizer=synth,
    )

    return Orchestrator(
        strategy=SingleAgentStrategy(),
        agents=[pipeline],
        timeout_seconds=settings.timeout_seconds,
    )


def _build_default_web_search_tool(settings: ChatSettings) -> WebSearchTool:
    provider: Any
    if settings.search_provider == "brave":
        if not settings.brave_api_key:
            raise ValueError(
                "search_provider='brave' requires BRAVE_API_KEY to be set"
            )
        provider = BraveSearchProvider(api_key=settings.brave_api_key)
    else:
        provider = DuckDuckGoSearchProvider()

    breaker = CircuitBreaker(
        failure_threshold=3,
        recovery_seconds=60.0,
        name=f"web_search:{settings.search_provider}",
    )
    return WebSearchTool(
        provider=provider,
        circuit_breaker=breaker,
        default_max_results=settings.max_search_results,
    )
