"""Tests for ``ContentFetcher`` — HTML/PDF text extraction over httpx."""

from __future__ import annotations

import httpx
import pytest

from src.orchestration.tools.web.content_fetcher import ContentFetcher


_HTML_PAGE = """
<html><head><title>Example</title>
<script>var x = 1;</script>
<style>body { color: red; }</style>
</head><body>
<h1>Heading One</h1>
<p>This is the first paragraph with enough characters to be kept by the parser.</p>
<p>tiny</p>
<div>Another long block that should also survive the minimum-length filter.</div>
</body></html>
"""


@pytest.mark.asyncio
async def test_fetch_extracts_readable_text_from_html() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text=_HTML_PAGE,
            headers={"content-type": "text/html; charset=utf-8"},
        )

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    fetcher = ContentFetcher(client=client)

    text = await fetcher.fetch("https://example.com/")

    assert "Heading One" in text
    assert "first paragraph" in text
    assert "tiny" not in text  # filtered by min-length
    assert "var x" not in text  # script content skipped
    await client.aclose()


@pytest.mark.asyncio
async def test_fetch_truncates_to_max_chars() -> None:
    """Truncation is whole-block: the loop stops after first block crosses the cap."""
    # Twenty paragraphs of ~100 chars each. max_chars=150 should keep ~2 blocks.
    paragraphs = "".join(
        f"<p>Paragraph number {i} contains text content that is long enough "
        f"to survive the minimum-length filter applied by the parser.</p>"
        for i in range(20)
    )
    body = f"<html><body>{paragraphs}</body></html>"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=body, headers={"content-type": "text/html"})

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    fetcher = ContentFetcher(client=client)

    full = await fetcher.fetch("https://example.com/", max_chars=20_000)
    truncated = await fetcher.fetch("https://example.com/", max_chars=150)

    assert len(truncated) < len(full)
    # 2 paragraphs at ~100 chars each: well under 4× max_chars.
    assert len(truncated) < 600
    await client.aclose()


@pytest.mark.asyncio
async def test_fetch_returns_empty_for_non_html_non_pdf() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b'{"hello": "world"}',
            headers={"content-type": "application/json"},
        )

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    fetcher = ContentFetcher(client=client)
    assert await fetcher.fetch("https://api.example.com/data.json") == ""
    await client.aclose()


@pytest.mark.asyncio
async def test_fetch_raises_on_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, content=b"missing")

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    fetcher = ContentFetcher(client=client)
    with pytest.raises(httpx.HTTPStatusError):
        await fetcher.fetch("https://example.com/missing")
    await client.aclose()


def test_extract_page_text_dedupes_repeated_blocks() -> None:
    html = (
        "<html><body>"
        "<p>The exact same sentence appears twice on this page.</p>"
        "<p>The exact same sentence appears twice on this page.</p>"
        "</body></html>"
    )
    text = ContentFetcher.extract_page_text(html)
    # The dedupe is case-insensitive, so we should see the sentence exactly once.
    assert text.lower().count("the exact same sentence") == 1
