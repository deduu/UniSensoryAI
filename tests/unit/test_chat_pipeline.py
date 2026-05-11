"""Tests for ``ChatPipelineAgent`` — the hybrid-routed composite."""

from __future__ import annotations

import json

import pytest

from src.chat.agents.chat_pipeline import ChatPipelineAgent
from src.chat.agents.direct_answerer import DirectAnswererAgent
from src.chat.agents.query_analyzer import QueryAnalyzerAgent
from src.chat.agents.synthesizer import SynthesizerAgent
from src.chat.agents.web_researcher import WebResearcherAgent
from src.orchestration.llm.mock import MockLLMProvider
from src.orchestration.models.context import AgentContext, ToolInput
from src.orchestration.models.results import ToolResult
from src.orchestration.tools.web.models import WebSearchResult


class _StubSearch:
    name = "web_search"

    def __init__(self, results: list[dict]) -> None:
        self._results = results
        self.calls: list[str] = []

    async def execute(self, tool_input: ToolInput) -> ToolResult:
        self.calls.append(tool_input.parameters["query"])
        return ToolResult(
            tool_name=self.name,
            output=self._results,
            success=True,
            metadata={"provider": "stub", "result_count": len(self._results)},
        )


class _StubFetcher:
    def __init__(self, bodies: dict[str, str]) -> None:
        self._bodies = bodies

    async def fetch(self, url: str, *, max_chars: int = 20000) -> str:
        return self._bodies.get(url, "")


def _build_pipeline(
    *,
    analyzer_llm: MockLLMProvider,
    answer_llm: MockLLMProvider,
    synth_llm: MockLLMProvider,
    search: _StubSearch,
    fetcher: _StubFetcher,
) -> ChatPipelineAgent:
    return ChatPipelineAgent(
        analyzer=QueryAnalyzerAgent(llm=analyzer_llm),
        direct_answerer=DirectAnswererAgent(llm=answer_llm),
        web_researcher=WebResearcherAgent(
            web_search=search, content_fetcher=fetcher, max_pages=2
        ),
        synthesizer=SynthesizerAgent(llm=synth_llm),
    )


@pytest.mark.asyncio
async def test_pipeline_takes_direct_path_when_analyzer_says_direct() -> None:
    analyzer = MockLLMProvider(
        responses=[json.dumps({"query_type": "direct", "refined_queries": ["x"]})]
    )
    answer = MockLLMProvider(responses=["42"])
    synth = MockLLMProvider(responses=["should not be called"])
    search = _StubSearch(results=[])
    fetcher = _StubFetcher(bodies={})

    pipeline = _build_pipeline(
        analyzer_llm=analyzer, answer_llm=answer, synth_llm=synth,
        search=search, fetcher=fetcher,
    )
    result = await pipeline.run(AgentContext(user_message="2+2 plus 38?"))

    assert "42" in result.response
    assert result.metadata["query_type"] == "direct"
    assert result.metadata["citations"] == []
    assert search.calls == []
    assert synth.call_count == 0


@pytest.mark.asyncio
async def test_pipeline_takes_search_path_when_analyzer_says_search() -> None:
    analyzer = MockLLMProvider(
        responses=[
            json.dumps(
                {
                    "query_type": "search",
                    "refined_queries": ["python 3.13 release notes"],
                }
            )
        ]
    )
    answer = MockLLMProvider(responses=["should not run"])
    synth = MockLLMProvider(
        responses=["Python 3.13 ships a JIT compiler [1] and free-threaded build [2]."]
    )
    search = _StubSearch(
        results=[
            WebSearchResult(title="A", url="https://a.example", snippet="snip a").model_dump(),
            WebSearchResult(title="B", url="https://b.example", snippet="snip b").model_dump(),
        ]
    )
    fetcher = _StubFetcher(
        bodies={"https://a.example": "JIT details.", "https://b.example": "Threading details."}
    )

    pipeline = _build_pipeline(
        analyzer_llm=analyzer, answer_llm=answer, synth_llm=synth,
        search=search, fetcher=fetcher,
    )
    result = await pipeline.run(AgentContext(user_message="What's new in Python 3.13?"))

    assert search.calls == ["python 3.13 release notes"]
    assert "[1]" in result.response and "[2]" in result.response
    assert result.metadata["query_type"] == "search"
    citations = result.metadata["citations"]
    assert len(citations) == 2
    assert {c["url"] for c in citations} == {"https://a.example", "https://b.example"}
    assert answer.call_count == 0


@pytest.mark.asyncio
async def test_pipeline_takes_ambiguous_path_with_function_calling_tools() -> None:
    """Ambiguous queries hit the answerer but with web_search as a tool option."""
    analyzer = MockLLMProvider(
        responses=[json.dumps({"query_type": "ambiguous", "refined_queries": ["x"]})]
    )
    answer = MockLLMProvider(responses=["I think the answer is..."])
    synth = MockLLMProvider(responses=["should not be called"])
    search = _StubSearch(results=[])
    fetcher = _StubFetcher(bodies={})

    pipeline = _build_pipeline(
        analyzer_llm=analyzer, answer_llm=answer, synth_llm=synth,
        search=search, fetcher=fetcher,
    )
    result = await pipeline.run(AgentContext(user_message="something ambiguous"))

    assert "answer" in result.response.lower()
    assert result.metadata["query_type"] == "ambiguous"
    # In ambiguous mode the answerer should have been given the web_search tool.
    sent_tools = answer.last_kwargs["tools"]
    assert sent_tools is not None
    assert any(t["function"]["name"] == "web_search" for t in sent_tools)
    # Synthesizer must NOT run on the ambiguous path.
    assert synth.call_count == 0


@pytest.mark.asyncio
async def test_pipeline_falls_back_to_direct_path_when_search_yields_no_sources() -> None:
    """If research returns zero usable URLs, drop back to direct answer."""
    analyzer = MockLLMProvider(
        responses=[json.dumps({"query_type": "search", "refined_queries": ["q"]})]
    )
    answer = MockLLMProvider(responses=["best-effort direct answer"])
    synth = MockLLMProvider(responses=["should not run when no sources"])
    search = _StubSearch(results=[])  # no results
    fetcher = _StubFetcher(bodies={})

    pipeline = _build_pipeline(
        analyzer_llm=analyzer, answer_llm=answer, synth_llm=synth,
        search=search, fetcher=fetcher,
    )
    result = await pipeline.run(AgentContext(user_message="weird query"))

    assert result.metadata["query_type"] == "search"
    assert result.metadata.get("fell_back_to_direct") is True
    assert "best-effort" in result.response
    # Synth would only run if we had sources; with zero sources we skip it.
    assert synth.call_count == 0


@pytest.mark.asyncio
async def test_pipeline_metadata_always_includes_query_type_and_refined_queries() -> None:
    analyzer = MockLLMProvider(
        responses=[
            json.dumps({"query_type": "direct", "refined_queries": ["q1", "q2"]})
        ]
    )
    answer = MockLLMProvider(responses=["ok"])
    pipeline = _build_pipeline(
        analyzer_llm=analyzer,
        answer_llm=answer,
        synth_llm=MockLLMProvider(responses=[]),
        search=_StubSearch(results=[]),
        fetcher=_StubFetcher(bodies={}),
    )
    result = await pipeline.run(AgentContext(user_message="x"))

    assert result.metadata["query_type"] == "direct"
    assert result.metadata["refined_queries"] == ["q1", "q2"]
