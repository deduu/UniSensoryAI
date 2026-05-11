"""Web-research agent: search → fetch → assemble sources for the synthesizer.

Calls ``WebSearchTool`` once per refined query, deduplicates URLs across
results, and fetches the top ``max_pages`` page bodies in parallel. The
output is a structured ``sources`` list that the synthesizer turns into
grounded text with inline citations.

Per-URL fetch errors are tolerated: the source row stays (snippet only),
``body`` becomes empty, and the synthesizer still has the title/URL to
cite. One flaky page should not kill the whole research run.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Protocol

from src.orchestration.interfaces.agent import Agent
from src.orchestration.models.context import AgentContext, ToolInput
from src.orchestration.models.results import AgentResult, ToolResult

logger = logging.getLogger(__name__)


class _SearchToolLike(Protocol):
    """Structural type: the subset of ``WebSearchTool`` the researcher needs."""

    name: str

    async def execute(self, tool_input: ToolInput) -> ToolResult:
        ...


class _ContentFetcherLike(Protocol):
    async def fetch(self, url: str, *, max_chars: int = 20000) -> str:
        ...


class WebResearcherAgent(Agent):
    """Run the search-and-fetch step of the search pipeline.

    Args:
        web_search: A ``WebSearchTool`` (or anything with the same
            ``execute(ToolInput) -> ToolResult`` shape).
        content_fetcher: Page-body fetcher with an async ``fetch(url)``.
        max_pages: Cap on how many pages to fetch across all queries.
        results_per_query: Search results requested per refined query.
        fetch_max_chars: Per-page body cap passed to the fetcher.
    """

    def __init__(
        self,
        *,
        web_search: _SearchToolLike,
        content_fetcher: _ContentFetcherLike,
        max_pages: int = 4,
        results_per_query: int = 5,
        fetch_max_chars: int = 6_000,
    ) -> None:
        self._search = web_search
        self._fetcher = content_fetcher
        self._max_pages = max_pages
        self._results_per_query = results_per_query
        self._fetch_max_chars = fetch_max_chars

    @property
    def name(self) -> str:
        return "web_researcher"

    @property
    def description(self) -> str:
        return "Search the web for refined queries and fetch top result pages."

    async def run(self, context: AgentContext) -> AgentResult:
        queries = self._select_queries(context)
        gathered: list[dict[str, Any]] = []
        seen_urls: set[str] = set()

        for query in queries:
            search_result = await self._search.execute(
                ToolInput(
                    tool_name=self._search.name,
                    parameters={"query": query, "max_results": self._results_per_query},
                )
            )
            if not search_result.success:
                logger.warning(
                    "WebResearcher: search failed for %r (%s)", query, search_result.error
                )
                continue
            for row in (search_result.output or []):
                url = row.get("url")
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                gathered.append(
                    {
                        "title": row.get("title", ""),
                        "url": url,
                        "snippet": row.get("snippet", ""),
                        "body": "",
                        "query": query,
                    }
                )
                if len(gathered) >= self._max_pages:
                    break
            if len(gathered) >= self._max_pages:
                break

        if not gathered:
            return AgentResult(
                agent_name=self.name,
                response="",
                metadata={"sources": [], "queries": queries},
            )

        bodies = await asyncio.gather(
            *(self._safe_fetch(row["url"]) for row in gathered),
            return_exceptions=False,
        )
        for row, body in zip(gathered, bodies, strict=True):
            row["body"] = body

        response_text = "\n\n".join(
            f"[{i + 1}] {src['title']} ({src['url']})\n{src['body'] or src['snippet']}"
            for i, src in enumerate(gathered)
        )

        return AgentResult(
            agent_name=self.name,
            response=response_text,
            metadata={
                "sources": gathered,
                "queries": queries,
                "source_count": len(gathered),
            },
        )

    def _select_queries(self, context: AgentContext) -> list[str]:
        refined = context.metadata.get("refined_queries") or []
        cleaned = [str(q).strip() for q in refined if str(q).strip()]
        if cleaned:
            return cleaned
        return [context.user_message]

    async def _safe_fetch(self, url: str) -> str:
        try:
            return await self._fetcher.fetch(url, max_chars=self._fetch_max_chars)
        except Exception as exc:  # noqa: BLE001 — best-effort fetch
            logger.warning("WebResearcher: fetch failed for %s: %s", url, exc)
            return ""
