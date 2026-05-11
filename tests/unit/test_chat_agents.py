"""Tests for chat agents: QueryAnalyzer, DirectAnswerer, WebResearcher, Synthesizer.

Every agent uses ``MockLLMProvider`` and stub tools/fetchers so tests stay
deterministic and offline.
"""

from __future__ import annotations

import json

import pytest

from src.chat.agents.direct_answerer import DirectAnswererAgent
from src.chat.agents.query_analyzer import QueryAnalyzerAgent
from src.chat.agents.synthesizer import SynthesizerAgent
from src.chat.agents.web_researcher import WebResearcherAgent
from src.orchestration.llm.mock import MockLLMProvider
from src.orchestration.models.context import AgentContext, ToolInput
from src.orchestration.models.results import ToolResult
from src.orchestration.tools.web.models import WebSearchResult


# ---------------------------------------------------------------------------
# QueryAnalyzerAgent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_query_analyzer_extracts_query_type_and_refined_queries() -> None:
    llm_output = json.dumps(
        {
            "query_type": "search",
            "refined_queries": ["python 3.13 release notes", "python 3.13 features"],
            "reasoning": "User asks about latest release",
        }
    )
    llm = MockLLMProvider(responses=[llm_output])
    agent = QueryAnalyzerAgent(llm=llm)
    result = await agent.run(AgentContext(user_message="What's new in Python 3.13?"))

    assert result.metadata["query_type"] == "search"
    assert result.metadata["refined_queries"] == [
        "python 3.13 release notes",
        "python 3.13 features",
    ]
    # The analyzer always sends a JSON-mode request.
    assert llm.last_kwargs["response_format"] == {"type": "json_object"}


@pytest.mark.asyncio
async def test_query_analyzer_falls_back_when_llm_returns_garbage() -> None:
    """If the LLM doesn't produce valid JSON we must not crash the request."""
    llm = MockLLMProvider(responses=["not json"])
    agent = QueryAnalyzerAgent(llm=llm)
    result = await agent.run(AgentContext(user_message="hi"))

    # Default is ambiguous so the orchestrator picks the function-calling
    # path rather than guessing wrong.
    assert result.metadata["query_type"] == "ambiguous"
    assert result.metadata["refined_queries"] == ["hi"]


@pytest.mark.asyncio
async def test_query_analyzer_normalizes_unknown_query_type() -> None:
    llm = MockLLMProvider(
        responses=[json.dumps({"query_type": "wat", "refined_queries": ["x"]})]
    )
    agent = QueryAnalyzerAgent(llm=llm)
    result = await agent.run(AgentContext(user_message="x"))
    assert result.metadata["query_type"] == "ambiguous"


# ---------------------------------------------------------------------------
# DirectAnswererAgent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_direct_answerer_returns_llm_content() -> None:
    llm = MockLLMProvider(responses=["The answer is 42."])
    agent = DirectAnswererAgent(llm=llm)
    result = await agent.run(AgentContext(user_message="what is 2+2 plus 38?"))
    assert "42" in result.response
    assert result.token_usage["prompt_tokens"] > 0


@pytest.mark.asyncio
async def test_direct_answerer_includes_conversation_history() -> None:
    llm = MockLLMProvider(responses=["ok"])
    agent = DirectAnswererAgent(llm=llm)
    history = [
        {"role": "user", "content": "earlier message"},
        {"role": "assistant", "content": "earlier reply"},
    ]
    await agent.run(
        AgentContext(user_message="new message", conversation_history=history),
    )
    sent_messages = llm.calls[0]
    contents = [m.content for m in sent_messages]
    assert "earlier message" in contents
    assert "new message" in contents


# ---------------------------------------------------------------------------
# WebResearcherAgent
# ---------------------------------------------------------------------------


class _StubWebSearchTool:
    """Test double mirroring ``WebSearchTool.execute``."""

    name = "web_search"

    def __init__(self, results_per_query: dict[str, list[dict]]) -> None:
        self._results = results_per_query
        self.queries: list[str] = []

    async def execute(self, tool_input: ToolInput) -> ToolResult:
        query = tool_input.parameters["query"]
        self.queries.append(query)
        return ToolResult(
            tool_name=self.name,
            output=self._results.get(query, []),
            success=True,
            metadata={"provider": "stub", "result_count": len(self._results.get(query, []))},
        )


class _StubFetcher:
    def __init__(self, body_for_url: dict[str, str]) -> None:
        self._bodies = body_for_url
        self.fetched: list[str] = []

    async def fetch(self, url: str, *, max_chars: int = 20000) -> str:
        self.fetched.append(url)
        return self._bodies.get(url, "")


@pytest.mark.asyncio
async def test_web_researcher_searches_and_fetches_top_results() -> None:
    search = _StubWebSearchTool(
        {
            "python 3.13 release notes": [
                WebSearchResult(title="A", url="https://a.example", snippet="snip a").model_dump(),
                WebSearchResult(title="B", url="https://b.example", snippet="snip b").model_dump(),
            ],
        }
    )
    fetcher = _StubFetcher(
        {"https://a.example": "Body of A.", "https://b.example": "Body of B."}
    )
    agent = WebResearcherAgent(web_search=search, content_fetcher=fetcher, max_pages=2)

    context = AgentContext(
        user_message="What's new in Python 3.13?",
        metadata={"refined_queries": ["python 3.13 release notes"]},
    )
    result = await agent.run(context)

    assert search.queries == ["python 3.13 release notes"]
    assert set(fetcher.fetched) == {"https://a.example", "https://b.example"}
    sources = result.metadata["sources"]
    assert [s["url"] for s in sources] == ["https://a.example", "https://b.example"]
    assert sources[0]["body"] == "Body of A."


@pytest.mark.asyncio
async def test_web_researcher_falls_back_to_user_message_when_no_refined_queries() -> None:
    search = _StubWebSearchTool({"original question": []})
    fetcher = _StubFetcher({})
    agent = WebResearcherAgent(web_search=search, content_fetcher=fetcher)
    await agent.run(AgentContext(user_message="original question"))
    assert search.queries == ["original question"]


@pytest.mark.asyncio
async def test_web_researcher_tolerates_individual_fetch_errors() -> None:
    """If one URL fails, others still surface — research is best-effort."""

    class _FlakyFetcher:
        async def fetch(self, url: str, *, max_chars: int = 20000) -> str:
            if "fail" in url:
                raise RuntimeError("404")
            return "good body"

    search = _StubWebSearchTool(
        {
            "q": [
                WebSearchResult(title="X", url="https://fail.example", snippet="x").model_dump(),
                WebSearchResult(title="Y", url="https://ok.example", snippet="y").model_dump(),
            ]
        }
    )
    agent = WebResearcherAgent(
        web_search=search,
        content_fetcher=_FlakyFetcher(),
        max_pages=2,
    )
    result = await agent.run(
        AgentContext(user_message="q", metadata={"refined_queries": ["q"]})
    )

    sources = result.metadata["sources"]
    # The failing fetch still contributes a source (snippet only); only the
    # body is empty.
    fail_source = next(s for s in sources if "fail" in s["url"])
    ok_source = next(s for s in sources if "ok" in s["url"])
    assert fail_source["body"] == ""
    assert ok_source["body"] == "good body"


# ---------------------------------------------------------------------------
# SynthesizerAgent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_synthesizer_grounds_response_in_sources_and_returns_citations() -> None:
    llm = MockLLMProvider(
        responses=[
            "Python 3.13 introduces a new JIT compiler and improved error messages [1]. "
            "It also ships a free-threaded build [2]."
        ]
    )
    agent = SynthesizerAgent(llm=llm)
    sources = [
        {"title": "Python 3.13 release notes", "url": "https://a.example", "snippet": "...", "body": "JIT compiler details."},
        {"title": "What's new in Python", "url": "https://b.example", "snippet": "...", "body": "Free-threaded build details."},
    ]
    context = AgentContext(
        user_message="What's new in Python 3.13?",
        metadata={"sources": sources, "refined_queries": ["python 3.13"]},
    )
    result = await agent.run(context)

    assert "[1]" in result.response
    assert "[2]" in result.response
    citations = result.metadata["citations"]
    assert len(citations) == 2
    assert citations[0]["url"] == "https://a.example"
    # The prompt sent to the LLM must mention both sources.
    prompt = "\n".join(m.content for m in llm.calls[0])
    assert "a.example" in prompt
    assert "b.example" in prompt


@pytest.mark.asyncio
async def test_synthesizer_handles_no_sources() -> None:
    """If the researcher came back empty, the synthesizer says so rather than hallucinating."""
    llm = MockLLMProvider(responses=["I couldn't find sources for that."])
    agent = SynthesizerAgent(llm=llm)
    result = await agent.run(
        AgentContext(user_message="obscure query", metadata={"sources": []}),
    )
    assert "couldn't find" in result.response.lower() or "no sources" in result.response.lower()
    assert result.metadata["citations"] == []
