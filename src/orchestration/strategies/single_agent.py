"""Run exactly one registered agent."""

from __future__ import annotations

from src.orchestration.interfaces.agent import Agent
from src.orchestration.models.context import AgentContext
from src.orchestration.models.results import AgentResult


class SingleAgentStrategy:
    """Delegates to the single agent in the orchestrator's registry.

    Useful when the orchestrator wraps a composite agent that does its own
    internal routing — the outer orchestrator just enforces the timeout.
    """

    async def execute(
        self,
        agents: list[Agent],
        context: AgentContext,
    ) -> AgentResult:
        if len(agents) != 1:
            raise ValueError(
                f"SingleAgentStrategy requires exactly one agent, got {len(agents)}"
            )
        return await agents[0].run(context)
