"""DuckDuckGo HTML-scraping search provider.

No API key required. Uses the same fallback shape as the original
``src.policy.web_search.WebSearchTool`` — POST/GET against the HTML and
lite endpoints until one returns parsable results.
"""

from __future__ import annotations

import httpx

from src.orchestration.tools.web._html_parsers import DuckDuckGoHTMLResultParser
from src.orchestration.tools.web.models import WebSearchResult
from src.orchestration.tools.web.providers.base import SearchProvider

_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
)


class DuckDuckGoSearchProvider(SearchProvider):
    """Scrape DuckDuckGo's HTML SERPs for offline-friendly search.

    Args:
        base_url: HTML SERP endpoint (default: html.duckduckgo.com).
        lite_url: Fallback endpoint used when ``base_url`` returns nothing.
        timeout_seconds: Per-request timeout.
        user_agent: Spoofed UA — DDG sometimes blocks empty UA strings.
        client: Optional pre-built ``httpx.AsyncClient``; mainly for tests.
            When supplied, the provider does NOT own its lifecycle and
            won't close it. When omitted, a client is built per ``search``.
    """

    def __init__(
        self,
        *,
        base_url: str = "https://html.duckduckgo.com/html/",
        lite_url: str = "https://lite.duckduckgo.com/lite/",
        timeout_seconds: float = 10.0,
        user_agent: str = _DEFAULT_USER_AGENT,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url
        self._lite_url = lite_url
        self._timeout_seconds = timeout_seconds
        self._user_agent = user_agent
        self._client = client

    @property
    def name(self) -> str:
        return "duckduckgo"

    async def search(
        self,
        query: str,
        *,
        max_results: int = 5,
    ) -> list[WebSearchResult]:
        """Run a search, trying four request shapes before giving up."""
        owned = self._client is None
        client = self._client or httpx.AsyncClient(
            follow_redirects=True,
            timeout=self._timeout_seconds,
            headers=self._default_headers(),
        )
        try:
            return await self._search_with_fallbacks(query, max_results, client)
        finally:
            if owned:
                await client.aclose()

    async def _search_with_fallbacks(
        self,
        query: str,
        max_results: int,
        client: httpx.AsyncClient,
    ) -> list[WebSearchResult]:
        attempts = [
            ("POST", self._base_url, {"data": {"q": query}}),
            ("GET", self._base_url, {"params": {"q": query}}),
            ("POST", self._lite_url, {"data": {"q": query}}),
            ("GET", self._lite_url, {"params": {"q": query}}),
        ]
        errors: list[str] = []

        for method, url, kwargs in attempts:
            try:
                response = await client.request(method, url, **kwargs)
                response.raise_for_status()
                results = self.parse_html(response.text, limit=max_results)
                if results:
                    return results
                errors.append(f"{method} {url} returned no parsable results")
            except httpx.HTTPStatusError as exc:
                errors.append(
                    f"{method} {url} returned "
                    f"{exc.response.status_code} {exc.response.reason_phrase}"
                )
            except httpx.HTTPError as exc:
                errors.append(
                    f"{method} {url} failed with {exc.__class__.__name__}: {exc}"
                )

        raise RuntimeError(
            "DuckDuckGo search failed after fallback attempts: " + "; ".join(errors)
        )

    def _default_headers(self) -> dict[str, str]:
        return {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "User-Agent": self._user_agent,
        }

    @classmethod
    def parse_html(cls, html: str, *, limit: int) -> list[WebSearchResult]:
        """Parse a DuckDuckGo SERP into structured results.

        Deduplicates on URL, caps at ``limit``, and tags every result with
        ``provider="duckduckgo"``.
        """
        parser = DuckDuckGoHTMLResultParser()
        parser.feed(html)
        parser.close()

        results: list[WebSearchResult] = []
        seen: set[str] = set()
        for raw in parser.results:
            url = raw["url"]
            if url in seen:
                continue
            seen.add(url)
            results.append(
                WebSearchResult(
                    title=raw["title"],
                    url=url,
                    snippet=raw["snippet"],
                    provider="duckduckgo",
                )
            )
            if len(results) >= limit:
                break
        return results
