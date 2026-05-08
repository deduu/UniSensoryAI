"""Tests for web search tool and web-backed policy agent."""

from __future__ import annotations

import httpx
import pytest

from src.policy.agents import WebSearchPolicyReferenceAgent
from src.policy.models import PolicyAgentResult, PolicyReviewContext, WebSearchResult
from src.policy.web_search import WebSearchTool


class FakeWebSearchTool:
    def __init__(
        self,
        results: list[WebSearchResult],
        *,
        page_text_by_url: dict[str, str] | None = None,
    ) -> None:
        self._results = results
        self.queries: list[str] = []
        self.page_text_by_url = page_text_by_url or {}

    async def search(self, query: str, *, max_results: int | None = None) -> list[WebSearchResult]:
        self.queries.append(query)
        return self._results[: max_results or len(self._results)]

    async def fetch_page_text(self, url: str, *, max_chars: int = 20000) -> str:
        return self.page_text_by_url.get(url, "")[:max_chars]


class FailingWebSearchTool:
    async def search(self, query: str, *, max_results: int | None = None) -> list[WebSearchResult]:
        raise RuntimeError("403 Forbidden")


def test_parse_duckduckgo_html_extracts_results():
    html = """
    <html>
      <body>
        <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fpolicy">
          Example Policy
        </a>
        <a class="result__snippet">Employees must not share customer data with vendors.</a>
      </body>
    </html>
    """

    results = WebSearchTool.parse_duckduckgo_html(html, limit=3)

    assert len(results) == 1
    assert results[0].title == "Example Policy"
    assert results[0].url == "https://example.com/policy"
    assert "must not share customer data" in results[0].snippet


def test_extract_page_text_reads_visible_policy_content():
    html = """
    <html>
      <body>
        <nav>Home</nav>
        <main>
          <h1>Data Policy</h1>
          <p>Employees must not share customer data with vendors.</p>
          <script>ignore me</script>
        </main>
      </body>
    </html>
    """

    text = WebSearchTool.extract_page_text(html)

    assert "Data Policy" in text
    assert "Employees must not share customer data with vendors." in text
    assert "ignore me" not in text


@pytest.mark.asyncio
async def test_web_search_tool_retries_after_403():
    html = """
    <html>
      <body>
        <a href="https://example.com/policy">Example Policy</a>
        <div>Employees must not share customer data with vendors.</div>
      </body>
    </html>
    """
    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, str(request.url)))
        if len(calls) == 1:
            return httpx.Response(403, request=request)
        return httpx.Response(200, text=html, request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, follow_redirects=True) as client:
        tool = WebSearchTool(client=client)
        results = await tool.search("customer data")

    assert len(results) == 1
    assert results[0].url == "https://example.com/policy"
    assert calls[0][0] == "POST"
    assert len(calls) >= 2


@pytest.mark.asyncio
async def test_web_search_agent_returns_conflicting_web_finding():
    search_tool = FakeWebSearchTool(
        results=[
            WebSearchResult(
                title="Public Data Policy",
                url="https://example.com/public-policy",
                snippet="Employees must not share customer data with vendors.",
            )
        ],
        page_text_by_url={
            "https://example.com/public-policy": (
                "Public Data Policy\n"
                "Employees must not share customer data with vendors."
            )
        },
    )
    agent = WebSearchPolicyReferenceAgent(search_tool=search_tool)
    context = PolicyReviewContext(
        job_id="job-1",
        policy_document_id="doc-1",
        policy_filename="new-policy.pdf",
        policy_text="Employees may share customer data with vendors for support.",
        include_web_search=True,
        focus="privacy",
    )

    result = await agent.review(context)

    assert result.agent_name == "web_search_policy_reference"
    assert len(result.findings) == 1
    assert result.findings[0].source == "web_search"
    assert result.findings[0].clauses[1].location == "https://example.com/public-policy"
    assert result.findings[0].metadata["reference_excerpt_source"] == "page_text"
    assert "Public Data Policy" in result.findings[0].description
    assert search_tool.queries


@pytest.mark.asyncio
async def test_web_search_agent_skips_when_not_requested():
    agent = WebSearchPolicyReferenceAgent(
        search_tool=FakeWebSearchTool(results=[])
    )
    context = PolicyReviewContext(
        job_id="job-1",
        policy_document_id="doc-1",
        policy_filename="policy.pdf",
        policy_text="Employees may share customer data with vendors for support.",
        include_web_search=False,
    )

    result = await agent.review(context)

    assert result == PolicyAgentResult(
        agent_name="web_search_policy_reference",
        notes=["Web search review was not requested."],
        metadata={"skipped": True},
    )


@pytest.mark.asyncio
async def test_web_search_agent_marks_result_degraded_when_queries_fail():
    agent = WebSearchPolicyReferenceAgent(search_tool=FailingWebSearchTool())
    context = PolicyReviewContext(
        job_id="job-1",
        policy_document_id="doc-1",
        policy_filename="policy.pdf",
        policy_text="Student records may be pasted into public AI tools.",
        include_web_search=True,
    )

    result = await agent.review(context)

    assert result.agent_name == "web_search_policy_reference"
    assert result.findings == []
    assert result.metadata["degraded"] is True
    assert result.metadata["failed_queries"] >= 1
    assert any("Public web evidence was unavailable" in note for note in result.notes)
