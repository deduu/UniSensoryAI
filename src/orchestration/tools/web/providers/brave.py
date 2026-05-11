"""Brave Search API provider.

Brave's web-search API returns JSON, gated by an
``X-Subscription-Token`` header. Each ``web.results[]`` row has a
``description`` field that may contain ``<strong>`` highlight markup;
we strip it for downstream consumers.
"""

from __future__ import annotations

import httpx

from src.orchestration.tools.web._html_parsers import strip_html_tags
from src.orchestration.tools.web.models import WebSearchResult
from src.orchestration.tools.web.providers.base import SearchProvider

_DEFAULT_BASE_URL = "https://api.search.brave.com/res/v1/web/search"


class BraveSearchProvider(SearchProvider):
    """Brave Search API client.

    Args:
        api_key: Brave subscription token. Required.
        base_url: Endpoint override (mainly for tests).
        timeout_seconds: Per-request timeout.
        client: Optional pre-built ``httpx.AsyncClient``; not closed by
            the provider when supplied.
    """

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = _DEFAULT_BASE_URL,
        timeout_seconds: float = 10.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("Brave Search requires a non-empty API key")
        self._api_key = api_key
        self._base_url = base_url
        self._timeout_seconds = timeout_seconds
        self._client = client

    @property
    def name(self) -> str:
        return "brave"

    async def search(
        self,
        query: str,
        *,
        max_results: int = 5,
    ) -> list[WebSearchResult]:
        # Brave caps ``count`` at 20; clamp our request so it never 400s.
        count = max(1, min(int(max_results), 20))
        owned = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self._timeout_seconds)
        try:
            response = await client.get(
                self._base_url,
                headers={
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip",
                    "X-Subscription-Token": self._api_key,
                },
                params={"q": query, "count": count},
            )
            response.raise_for_status()
            payload = response.json()
        finally:
            if owned:
                await client.aclose()

        rows = (payload.get("web") or {}).get("results") or []
        results: list[WebSearchResult] = []
        for row in rows[:max_results]:
            url = row.get("url") or ""
            if not url:
                continue
            results.append(
                WebSearchResult(
                    title=row.get("title") or "",
                    url=url,
                    snippet=strip_html_tags(row.get("description") or ""),
                    provider="brave",
                )
            )
        return results
