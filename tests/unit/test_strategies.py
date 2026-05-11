"""Tests for orchestration strategies.

Each strategy is a pure function from ``(agents, context)`` to an
``AgentResult``. The strategies use ``Agent`` instances composed of
``_FakeAgent`` subclasses defined here to keep tests deterministic and
free of LLM calls.
"""

from __future__ import annotations

import asyncio

import pytest

from src.orchestration.interfaces.agent import Agent
from src.orchestration.models.context import AgentContext
from src.orchestration.models.results import AgentResult
from src.orchestration.strategies.parallel import ParallelStrategy
from src.orchestration.strategies.pipeline import PipelineStrategy
from src.orchestration.strategies.router import RouterStrategy
from src.orchestration.strategies.single_agent import SingleAgentStrategy


class _FakeAgent(Agent):
    def __init__(
        self,
        agent_name: str,
        *,
        response: str = "ok",
        delay: float = 0.0,
        raise_exc: Exception | None = None,
    ) -> None:
        self._name = agent_name
        self._response = response
        self._delay = delay
        self._raise = raise_exc
        self.call_count = 0
        self.last_context: AgentContext | None = None

    @property
    def name(self) -> str:
        return self._name

    async def run(self, context: AgentContext) -> AgentResult:
        self.call_count += 1
        self.last_context = context
        if self._delay:
            await asyncio.sleep(self._delay)
        if self._raise is not None:
            raise self._raise
        return AgentResult(
            agent_name=self._name,
            response=self._response,
            metadata={"input": context.user_message, "agent": self._name},
        )


# ---------------------------------------------------------------------------
# SingleAgent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_single_agent_runs_first_agent() -> None:
    a = _FakeAgent("a", response="hello")
    result = await SingleAgentStrategy().execute([a], AgentContext(user_message="hi"))
    assert result.response == "hello"
    assert a.call_count == 1


@pytest.mark.asyncio
async def test_single_agent_requires_exactly_one_agent() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        await SingleAgentStrategy().execute([], AgentContext(user_message="x"))

    a, b = _FakeAgent("a"), _FakeAgent("b")
    with pytest.raises(ValueError, match="exactly one"):
        await SingleAgentStrategy().execute([a, b], AgentContext(user_message="x"))


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_router_dispatches_by_routing_function() -> None:
    a = _FakeAgent("alpha", response="A")
    b = _FakeAgent("beta", response="B")

    def route(ctx: AgentContext, agents: list[Agent]) -> Agent:
        return next(agent for agent in agents if agent.name == ctx.metadata["pick"])

    strategy = RouterStrategy(route_fn=route)
    result = await strategy.execute([a, b], AgentContext(user_message="x", metadata={"pick": "beta"}))
    assert result.response == "B"
    assert a.call_count == 0
    assert b.call_count == 1


@pytest.mark.asyncio
async def test_router_raises_when_function_returns_unknown_agent() -> None:
    a = _FakeAgent("alpha")
    other = _FakeAgent("other")

    strategy = RouterStrategy(route_fn=lambda _ctx, _agents: other)
    with pytest.raises(ValueError, match="route_fn returned"):
        await strategy.execute([a], AgentContext(user_message="x"))


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pipeline_runs_agents_sequentially_threading_results() -> None:
    """Each agent sees the prior agent's response in metadata."""

    class _Recording(Agent):
        def __init__(self, n: str) -> None:
            self._n = n
            self.seen_prior: str | None = None

        @property
        def name(self) -> str:
            return self._n

        async def run(self, context: AgentContext) -> AgentResult:
            self.seen_prior = context.metadata.get("previous_response")
            return AgentResult(
                agent_name=self._n,
                response=f"{self._n}-out",
                metadata={"agent": self._n},
            )

    a = _Recording("a")
    b = _Recording("b")
    c = _Recording("c")

    result = await PipelineStrategy().execute([a, b, c], AgentContext(user_message="x"))

    assert result.response == "c-out"
    assert a.seen_prior is None
    assert b.seen_prior == "a-out"
    assert c.seen_prior == "b-out"
    # The combined result advertises the pipeline.
    assert result.metadata["pipeline"] == ["a", "b", "c"]


@pytest.mark.asyncio
async def test_pipeline_short_circuits_on_agent_failure() -> None:
    a = _FakeAgent("a")
    b = _FakeAgent("b", raise_exc=RuntimeError("middle blew up"))
    c = _FakeAgent("c")

    with pytest.raises(RuntimeError, match="middle"):
        await PipelineStrategy().execute([a, b, c], AgentContext(user_message="x"))

    assert a.call_count == 1
    assert b.call_count == 1
    assert c.call_count == 0


# ---------------------------------------------------------------------------
# Parallel
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_parallel_gathers_all_and_merges_metadata() -> None:
    a = _FakeAgent("a", response="A", delay=0.005)
    b = _FakeAgent("b", response="B", delay=0.005)

    result = await ParallelStrategy().execute([a, b], AgentContext(user_message="x"))

    assert result.agent_name == "parallel"
    assert "A" in result.response and "B" in result.response
    assert set(result.metadata["agents"]) == {"a", "b"}
    assert a.call_count == 1 and b.call_count == 1


@pytest.mark.asyncio
async def test_parallel_records_agent_exceptions_as_failures() -> None:
    a = _FakeAgent("a", response="ok")
    b = _FakeAgent("b", raise_exc=RuntimeError("b failed"))

    result = await ParallelStrategy().execute([a, b], AgentContext(user_message="x"))
    failures = result.metadata.get("failures", {})

    assert "b" in failures
    assert "b failed" in failures["b"]
    # The successful agent's response is still surfaced.
    assert "ok" in result.response


@pytest.mark.asyncio
async def test_parallel_actually_runs_concurrently() -> None:
    """Two 50ms agents should finish in well under 100ms when parallel."""
    a = _FakeAgent("a", delay=0.05)
    b = _FakeAgent("b", delay=0.05)

    start = asyncio.get_running_loop().time()
    await ParallelStrategy().execute([a, b], AgentContext(user_message="x"))
    elapsed = asyncio.get_running_loop().time() - start
    assert elapsed < 0.09
