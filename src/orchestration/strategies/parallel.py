"""Fan agents out via ``asyncio.gather``; merge their results."""

from __future__ import annotations

import asyncio

from src.orchestration.interfaces.agent import Agent
from src.orchestration.models.context import AgentContext
from src.orchestration.models.results import AgentResult


class ParallelStrategy:
    """Run every registered agent concurrently and merge their outputs.

    Successful agent responses are concatenated (newline-separated) and
    each agent's metadata is preserved under ``metadata["results"]``.
    Per-agent exceptions are caught and recorded in
    ``metadata["failures"]`` keyed by agent name; one failing agent does
    not abort the others, mirroring ``ParallelPolicyReviewOrchestrator``.

    Use this when *every* agent has something independent to contribute
    (e.g. multiple research angles). When you only want one of N answers,
    use ``RouterStrategy`` instead.
    """

    async def execute(
        self,
        agents: list[Agent],
        context: AgentContext,
    ) -> AgentResult:
        if not agents:
            raise ValueError("ParallelStrategy requires at least one agent")

        coros = [agent.run(context) for agent in agents]
        outcomes = await asyncio.gather(*coros, return_exceptions=True)

        responses: list[str] = []
        per_agent_metadata: dict[str, dict] = {}
        failures: dict[str, str] = {}
        token_totals: dict[str, int] = {}

        for agent, outcome in zip(agents, outcomes, strict=True):
            if isinstance(outcome, BaseException):
                failures[agent.name] = f"{outcome.__class__.__name__}: {outcome}"
                continue
            responses.append(outcome.response)
            per_agent_metadata[agent.name] = outcome.metadata
            for key, value in outcome.token_usage.items():
                token_totals[key] = token_totals.get(key, 0) + value

        return AgentResult(
            agent_name="parallel",
            response="\n\n".join(responses),
            metadata={
                "agents": [a.name for a in agents],
                "results": per_agent_metadata,
                "failures": failures,
            },
            token_usage=token_totals,
        )
