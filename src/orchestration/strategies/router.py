"""Pick one agent per request via a caller-supplied routing function."""

from __future__ import annotations

from typing import Callable

from src.orchestration.interfaces.agent import Agent
from src.orchestration.models.context import AgentContext
from src.orchestration.models.results import AgentResult

RouteFn = Callable[[AgentContext, list[Agent]], Agent]


class RouterStrategy:
    """Dispatch each request to one of ``agents`` chosen by ``route_fn``.

    Args:
        route_fn: Sync function that returns the agent to run. Must return
            an agent present in the registry — otherwise we raise instead of
            silently picking a default, since misroutes are usually bugs.
    """

    def __init__(self, route_fn: RouteFn) -> None:
        self._route_fn = route_fn

    async def execute(
        self,
        agents: list[Agent],
        context: AgentContext,
    ) -> AgentResult:
        chosen = self._route_fn(context, agents)
        if chosen not in agents:
            raise ValueError(
                f"route_fn returned agent {chosen.name!r} not in registry"
            )
        return await chosen.run(context)
