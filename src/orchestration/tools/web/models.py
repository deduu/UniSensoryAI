"""Public data types for web-search results."""

from __future__ import annotations

from pydantic import BaseModel


class WebSearchResult(BaseModel):
    """A single result row from a search provider.

    Attributes:
        title: The result title as shown by the provider.
        url: Canonical destination URL (redirect wrappers are unwrapped
            by the provider).
        snippet: Short description text. Providers strip simple markup.
        provider: Identifier of the provider that produced the row,
            e.g. ``"duckduckgo"`` or ``"brave"``. Useful for downstream
            telemetry and source attribution.
    """

    title: str
    url: str
    snippet: str = ""
    provider: str = "duckduckgo"
