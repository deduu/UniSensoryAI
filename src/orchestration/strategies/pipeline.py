"""Run agents sequentially; thread each result into the next context."""

from __future__ import annotations

from src.orchestration.interfaces.agent import Agent
from src.orchestration.models.context import AgentContext
from src.orchestration.models.results import AgentResult


class PipelineStrategy:
    """Chain agents in registry order.

    Each downstream agent sees the prior agent's response and metadata via
    ``context.metadata`` (``previous_response`` plus any prior metadata
    keys, merged so later agents shadow earlier ones).

    The final ``AgentResult`` is the last agent's result, with the full
    pipeline order recorded under ``metadata["pipeline"]``.

    Exceptions short-circuit the pipeline; the failing agent's error
    propagates so the orchestrator's timeout/retry logic can decide how
    to handle it.
    """

    async def execute(
        self,
        agents: list[Agent],
        context: AgentContext,
    ) -> AgentResult:
        if not agents:
            raise ValueError("PipelineStrategy requires at least one agent")

        result: AgentResult | None = None
        current = context
        for agent in agents:
            if result is not None:
                merged_metadata = {
                    **current.metadata,
                    **result.metadata,
                    "previous_response": result.response,
                    "previous_agent": result.agent_name,
                }
                current = current.model_copy(update={"metadata": merged_metadata})
            result = await agent.run(current)

        # Mypy: agents is non-empty so result is guaranteed populated.
        assert result is not None
        return result.model_copy(
            update={
                "metadata": {**result.metadata, "pipeline": [a.name for a in agents]},
            }
        )
