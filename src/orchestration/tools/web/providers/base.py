"""Search-provider contract.

Concrete providers handle their own HTTP, auth, and result parsing. They
return a list of ``WebSearchResult`` ordered by relevance.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.orchestration.tools.web.models import WebSearchResult


class SearchProvider(ABC):
    """Base class for web-search backends.

    Providers are stateful (they cache an ``httpx.AsyncClient``, an API
    key, etc.) but stateless across calls — ``search`` must be safe to
    invoke from multiple coroutines concurrently.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier (``"duckduckgo"``, ``"brave"``, ...)."""

    @abstractmethod
    async def search(
        self,
        query: str,
        *,
        max_results: int = 5,
    ) -> list[WebSearchResult]:
        """Run a search.

        Args:
            query: Free-text query.
            max_results: Maximum rows to return; providers may return fewer.

        Returns:
            Results in provider-relevance order, capped at ``max_results``.
        """

    async def aclose(self) -> None:  # noqa: B027 — optional hook
        """Optional shutdown hook for owned httpx clients."""
