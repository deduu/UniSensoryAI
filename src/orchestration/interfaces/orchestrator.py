"""Orchestrator + pluggable strategy protocol."""

from __future__ import annotations

import asyncio
from typing import Protocol, runtime_checkable

from src.orchestration.interfaces.agent import Agent
from src.orchestration.models.context import AgentContext
from src.orchestration.models.results import AgentResult


@runtime_checkable
class OrchestratorStrategy(Protocol):
    """Structural type all strategies must satisfy.

    Strategies do not need to subclass anything — duck typing keeps the
    boundary small. Implementations decide *how* the agent registry is
    used (sequentially, in parallel, routed by a function, ...).
    """

    async def execute(
        self,
        agents: list[Agent],
        context: AgentContext,
    ) -> AgentResult:
        """Run the strategy and return a single combined ``AgentResult``."""


class Orchestrator:
    """Owns an agent registry, delegates to a swappable strategy.

    Per repo rule 9, the orchestrator caps each run at ``timeout_seconds``;
    callers can override per-request. The default of 30s matches the
    agent-timeout budget in ``CLAUDE.md``.
    """

    def __init__(
        self,
        strategy: OrchestratorStrategy,
        agents: list[Agent],
        *,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._strategy = strategy
        self._agents = agents
        self._timeout_seconds = timeout_seconds

    @property
    def strategy(self) -> OrchestratorStrategy:
        return self._strategy

    @strategy.setter
    def strategy(self, new_strategy: OrchestratorStrategy) -> None:
        self._strategy = new_strategy

    @property
    def agents(self) -> list[Agent]:
        return self._agents

    async def run(
        self,
        context: AgentContext,
        *,
        timeout_seconds: float | None = None,
    ) -> AgentResult:
        """Execute the current strategy with timeout enforcement.

        Args:
            context: Frozen context for this turn.
            timeout_seconds: Optional per-call override of the orchestrator
                default.

        Raises:
            asyncio.TimeoutError: If the strategy doesn't finish in time.
        """
        effective = self._timeout_seconds if timeout_seconds is None else timeout_seconds
        return await asyncio.wait_for(
            self._strategy.execute(self._agents, context),
            timeout=effective,
        )
