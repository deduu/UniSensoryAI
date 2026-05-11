"""Tests for ``src.orchestration.interfaces`` and ``src.orchestration.models``.

These tests intentionally exercise the *contract* of the abstractions, not
any concrete behaviour. They lock in:

- ABC enforcement: subclasses missing abstract members can't be instantiated.
- Frozen ``AgentContext`` rejects mutation (multi-agent safety).
- Pydantic defaults for ``ToolResult`` / ``AgentResult`` so callers can omit
  boilerplate.
- ``Orchestrator.run`` enforces its timeout via ``asyncio.wait_for``.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from pydantic import ValidationError

from src.orchestration.interfaces.agent import Agent
from src.orchestration.interfaces.orchestrator import (
    Orchestrator,
    OrchestratorStrategy,
)
from src.orchestration.interfaces.tool import Tool
from src.orchestration.models.context import AgentContext, ToolInput
from src.orchestration.models.results import AgentResult, ToolResult


# ---------------------------------------------------------------------------
# Tool ABC
# ---------------------------------------------------------------------------


def test_tool_abc_rejects_incomplete_subclass() -> None:
    """A subclass that doesn't implement every abstract member can't be built."""

    class Half(Tool):
        @property
        def name(self) -> str:
            return "half"

    with pytest.raises(TypeError):
        Half()  # type: ignore[abstract]


@pytest.mark.asyncio
async def test_tool_abc_complete_subclass_runs() -> None:
    """A fully concrete Tool subclass instantiates and runs."""

    class Echo(Tool):
        @property
        def name(self) -> str:
            return "echo"

        @property
        def description(self) -> str:
            return "Returns input"

        @property
        def input_schema(self) -> dict[str, Any]:
            return {"type": "object"}

        async def execute(self, tool_input: ToolInput) -> ToolResult:
            return ToolResult(tool_name=self.name, output=tool_input.parameters)

    tool = Echo()
    result = await tool.execute(ToolInput(tool_name="echo", parameters={"x": 1}))
    assert result.success is True
    assert result.output == {"x": 1}


# ---------------------------------------------------------------------------
# Agent ABC
# ---------------------------------------------------------------------------


def test_agent_abc_rejects_incomplete_subclass() -> None:
    class NoRun(Agent):
        @property
        def name(self) -> str:
            return "no-run"

    with pytest.raises(TypeError):
        NoRun()  # type: ignore[abstract]


@pytest.mark.asyncio
async def test_agent_abc_complete_subclass_runs() -> None:
    class Greeter(Agent):
        @property
        def name(self) -> str:
            return "greeter"

        async def run(self, context: AgentContext) -> AgentResult:
            return AgentResult(agent_name=self.name, response=f"hi {context.user_message}")

    agent = Greeter()
    out = await agent.run(AgentContext(user_message="world"))
    assert out.response == "hi world"
    assert out.agent_name == "greeter"


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


def test_agent_context_is_frozen() -> None:
    """Mutating an AgentContext field must raise — agents share the same context."""
    ctx = AgentContext(user_message="hello")
    with pytest.raises(ValidationError):
        ctx.user_message = "mutated"  # type: ignore[misc]


def test_agent_context_model_copy_update_returns_new_instance() -> None:
    """model_copy is the supported way to thread state through a pipeline."""
    ctx = AgentContext(user_message="a", metadata={"k": 1})
    updated = ctx.model_copy(update={"metadata": {**ctx.metadata, "k": 2}})
    assert ctx.metadata == {"k": 1}
    assert updated.metadata == {"k": 2}


def test_tool_input_requires_tool_name() -> None:
    with pytest.raises(ValidationError):
        ToolInput()  # type: ignore[call-arg]


def test_tool_result_success_default_true() -> None:
    r = ToolResult(tool_name="t", output=None)
    assert r.success is True
    assert r.error is None


def test_agent_result_defaults() -> None:
    r = AgentResult(agent_name="a", response="ok")
    assert r.request_id is not None
    assert r.created_at is not None
    assert r.tool_calls == []
    assert r.token_usage == {}


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


class _NoopStrategy:
    """Strategy that resolves to a fixed AgentResult after an optional delay."""

    def __init__(self, *, delay: float = 0.0, response: str = "done") -> None:
        self._delay = delay
        self._response = response

    async def execute(
        self, agents: list[Agent], context: AgentContext
    ) -> AgentResult:
        if self._delay:
            await asyncio.sleep(self._delay)
        return AgentResult(agent_name="noop", response=self._response)


def test_strategy_protocol_accepts_duck_typed_class() -> None:
    """Strategies don't inherit; the Protocol uses structural typing."""
    assert isinstance(_NoopStrategy(), OrchestratorStrategy)


@pytest.mark.asyncio
async def test_orchestrator_runs_strategy() -> None:
    orch = Orchestrator(strategy=_NoopStrategy(response="hello"), agents=[])
    result = await orch.run(AgentContext(user_message="x"))
    assert result.response == "hello"


@pytest.mark.asyncio
async def test_orchestrator_timeout_raises() -> None:
    """A strategy that exceeds the orchestrator's timeout must raise."""
    orch = Orchestrator(
        strategy=_NoopStrategy(delay=0.05),
        agents=[],
        timeout_seconds=0.01,
    )
    with pytest.raises(asyncio.TimeoutError):
        await orch.run(AgentContext(user_message="x"))


@pytest.mark.asyncio
async def test_orchestrator_per_call_timeout_override() -> None:
    """Caller can override the default timeout for a single run."""
    orch = Orchestrator(
        strategy=_NoopStrategy(delay=0.02),
        agents=[],
        timeout_seconds=10.0,
    )
    with pytest.raises(asyncio.TimeoutError):
        await orch.run(AgentContext(user_message="x"), timeout_seconds=0.005)


def test_orchestrator_strategy_is_swappable() -> None:
    orch = Orchestrator(strategy=_NoopStrategy(response="a"), agents=[])
    new_strategy = _NoopStrategy(response="b")
    orch.strategy = new_strategy
    assert orch.strategy is new_strategy
