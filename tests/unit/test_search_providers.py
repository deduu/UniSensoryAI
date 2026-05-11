"""Tests for the pluggable web-search providers.

Covers the ``SearchProvider`` ABC and its two shipped implementations
(``DuckDuckGoSearchProvider`` and ``BraveSearchProvider``). All network I/O
is mocked via ``httpx.MockTransport`` so the tests stay offline and
deterministic.
"""

from __future__ import annotations

import json

import httpx
import pytest

from src.orchestration.tools.web.models import WebSearchResult
from src.orchestration.tools.web.providers.base import SearchProvider
from src.orchestration.tools.web.providers.brave import BraveSearchProvider
from src.orchestration.tools.web.providers.duckduckgo import (
    DuckDuckGoSearchProvider,
)


# ---------------------------------------------------------------------------
# SearchProvider ABC
# ---------------------------------------------------------------------------


def test_search_provider_abc_rejects_incomplete_subclass() -> None:
    class Half(SearchProvider):
        @property
        def name(self) -> str:
            return "half"

    with pytest.raises(TypeError):
        Half()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# DuckDuckGo
# ---------------------------------------------------------------------------


_DDG_HTML = """
<html><body>
<div class="result">
  <a class="result__a" href="https://example.com/one">First Result</a>
  <div class="result__snippet">Snippet one body.</div>
</div>
<div class="result">
  <a class="result__a" href="https://example.com/two">Second</a>
  <div class="result__snippet">Snippet two body.</div>
</div>
<div class="result">
  <a class="result__a" href="https://example.com/one">First Duplicate</a>
  <div class="result__snippet">Different snippet but same url.</div>
</div>
</body></html>
"""


_DDG_REDIRECT_HTML = """
<html><body>
<div class="result">
  <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.org%2Fpath">Redirected</a>
  <div class="result__snippet">Wrapped via the DDG redirect.</div>
</div>
</body></html>
"""


def test_duckduckgo_parses_html_into_results() -> None:
    results = DuckDuckGoSearchProvider.parse_html(_DDG_HTML, limit=5)
    assert [r.title for r in results] == ["First Result", "Second"]
    assert all(isinstance(r, WebSearchResult) for r in results)
    assert results[0].url == "https://example.com/one"
    assert results[0].snippet == "Snippet one body."
    assert results[0].provider == "duckduckgo"


def test_duckduckgo_deduplicates_urls() -> None:
    """The third result reuses the first URL; it must be dropped."""
    results = DuckDuckGoSearchProvider.parse_html(_DDG_HTML, limit=5)
    urls = [r.url for r in results]
    assert len(urls) == len(set(urls))


def test_duckduckgo_respects_limit() -> None:
    results = DuckDuckGoSearchProvider.parse_html(_DDG_HTML, limit=1)
    assert len(results) == 1


def test_duckduckgo_normalizes_redirect_urls() -> None:
    results = DuckDuckGoSearchProvider.parse_html(_DDG_REDIRECT_HTML, limit=1)
    assert results[0].url == "https://example.org/path"


@pytest.mark.asyncio
async def test_duckduckgo_search_returns_results_through_http(monkeypatch: pytest.MonkeyPatch) -> None:
    """End-to-end: provider POSTs to the HTML endpoint and parses the body."""
    captured_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        return httpx.Response(200, text=_DDG_HTML, headers={"content-type": "text/html"})

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    provider = DuckDuckGoSearchProvider(client=client)

    results = await provider.search("python testing", max_results=2)

    assert len(results) == 2
    assert results[0].title == "First Result"
    # First attempt is POST to the html endpoint.
    assert captured_requests[0].method == "POST"
    assert "duckduckgo" in str(captured_requests[0].url)
    await client.aclose()


@pytest.mark.asyncio
async def test_duckduckgo_search_raises_when_all_attempts_fail() -> None:
    """All four request shapes fail → RuntimeError aggregating the errors."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    provider = DuckDuckGoSearchProvider(client=client)

    with pytest.raises(RuntimeError, match="DuckDuckGo"):
        await provider.search("query", max_results=2)
    await client.aclose()


# ---------------------------------------------------------------------------
# Brave
# ---------------------------------------------------------------------------


_BRAVE_BODY = {
    "web": {
        "results": [
            {
                "title": "First Brave",
                "url": "https://brave.example.com/one",
                "description": "<strong>brave</strong> snippet one",
            },
            {
                "title": "Second Brave",
                "url": "https://brave.example.com/two",
                "description": "brave snippet two",
            },
        ]
    }
}


def test_brave_requires_api_key() -> None:
    with pytest.raises(ValueError, match="API key"):
        BraveSearchProvider(api_key="")


@pytest.mark.asyncio
async def test_brave_sends_subscription_header_and_parses_response() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, content=json.dumps(_BRAVE_BODY).encode())

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    provider = BraveSearchProvider(api_key="secret-token", client=client)

    results = await provider.search("python", max_results=2)

    assert [r.title for r in results] == ["First Brave", "Second Brave"]
    assert all(r.provider == "brave" for r in results)
    # Brave strips simple HTML tags from descriptions.
    assert "<strong>" not in results[0].snippet

    sent = captured[0]
    assert sent.headers["X-Subscription-Token"] == "secret-token"
    assert sent.headers["Accept"] == "application/json"
    assert "python" in str(sent.url)
    await client.aclose()


@pytest.mark.asyncio
async def test_brave_respects_max_results() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=json.dumps(_BRAVE_BODY).encode())

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    provider = BraveSearchProvider(api_key="t", client=client)

    results = await provider.search("query", max_results=1)
    assert len(results) == 1
    await client.aclose()


@pytest.mark.asyncio
async def test_brave_handles_empty_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b'{"web": {"results": []}}')

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    provider = BraveSearchProvider(api_key="t", client=client)
    assert await provider.search("nothing", max_results=5) == []
    await client.aclose()


@pytest.mark.asyncio
async def test_brave_raises_on_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, content=b"rate limited")

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    provider = BraveSearchProvider(api_key="t", client=client)

    with pytest.raises(httpx.HTTPStatusError):
        await provider.search("q", max_results=1)
    await client.aclose()
