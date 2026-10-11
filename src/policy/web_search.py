"""Backwards-compat shim — delegates to ``src.orchestration.tools.web``.

Policy-era callers used a single ``WebSearchTool`` that combined searching,
page fetching, and parsing. The orchestration framework now splits those
into a pluggable ``SearchProvider`` and a separate ``ContentFetcher``. This
module keeps the old class name and method signatures so policy agents and
their tests work unchanged; new code should import from
``src.orchestration.tools.web`` directly.
"""

from __future__ import annotations

import httpx

from src.orchestration.tools.web.content_fetcher import ContentFetcher
from src.orchestration.tools.web.providers.duckduckgo import (
    DuckDuckGoSearchProvider,
)
from src.utils.config import ConfigLoader

from .models import WebSearchResult


class WebSearchTool:
    """Compat facade over the orchestration search provider + content fetcher.

    The public methods mirror the policy-era API:

    - ``search(query, *, max_results)`` → ``list[WebSearchResult]`` from the
      policy ``models`` module (not the orchestration variant).
    - ``fetch_page_text(url, *, max_chars)`` → readable text from an HTML or
      PDF page.
    - ``parse_duckduckgo_html`` / ``extract_page_text`` / ``extract_pdf_text``
      remain available as classmethods, delegating to the new providers.
    """

    def __init__(
        self,
        *,
        provider: str | None = None,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        max_results: int | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        policy_config = ConfigLoader.get_policy_config()
        web_config = policy_config.get("web_search", {})
        provider_name = (provider or web_config.get("provider", "duckduckgo")).lower()
        if provider_name != "duckduckgo":
            raise ValueError(f"Unsupported web search provider: {provider_name}")

        self._provider_name = provider_name
        self._timeout_seconds = float(
            timeout_seconds or web_config.get("timeout_seconds", 10.0)
        )
        self._max_results = int(max_results or web_config.get("max_results", 3))

        ddg_base = base_url or web_config.get(
            "base_url", "https://html.duckduckgo.com/html/"
        )
        ddg_lite = web_config.get("lite_url", "https://lite.duckduckgo.com/lite/")
        user_agent = web_config.get(
            "user_agent",
            (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
            ),
        )

        self._provider = DuckDuckGoSearchProvider(
            base_url=ddg_base,
            lite_url=ddg_lite,
            timeout_seconds=self._timeout_seconds,
            user_agent=user_agent,
            client=client,
        )
        self._fetcher = ContentFetcher(
            timeout_seconds=self._timeout_seconds,
            user_agent=user_agent,
            client=client,
        )

    async def search(
        self,
        query: str,
        *,
        max_results: int | None = None,
    ) -> list[WebSearchResult]:
        limit = max_results or self._max_results
        results = await self._provider.search(query, max_results=limit)
        return [
            WebSearchResult(
                title=r.title,
                url=r.url,
                snippet=r.snippet,
                provider=r.provider,
            )
            for r in results
        ]

    async def fetch_page_text(self, url: str, *, max_chars: int = 20000) -> str:
        return await self._fetcher.fetch(url, max_chars=max_chars)

    @classmethod
    def parse_duckduckgo_html(cls, html: str, *, limit: int) -> list[WebSearchResult]:
        return [
            WebSearchResult(
                title=r.title,
                url=r.url,
                snippet=r.snippet,
                provider=r.provider,
            )
            for r in DuckDuckGoSearchProvider.parse_html(html, limit=limit)
        ]

    @classmethod
    def extract_page_text(cls, html: str, *, max_chars: int = 20000) -> str:
        return ContentFetcher.extract_page_text(html, max_chars=max_chars)

    @classmethod
    def extract_pdf_text(cls, pdf_bytes: bytes, *, max_chars: int = 20000) -> str:
        return ContentFetcher.extract_pdf_text(pdf_bytes, max_chars=max_chars)
