"""Pluggable web-search backends.

Concrete providers (DuckDuckGo, Brave, ...) implement the
``SearchProvider`` ABC defined in ``base``. The active provider is
selected by ``WebSearchTool`` at construction.
"""

from src.orchestration.tools.web.providers.base import SearchProvider
from src.orchestration.tools.web.providers.brave import BraveSearchProvider
from src.orchestration.tools.web.providers.duckduckgo import (
    DuckDuckGoSearchProvider,
)

__all__ = ["BraveSearchProvider", "DuckDuckGoSearchProvider", "SearchProvider"]
