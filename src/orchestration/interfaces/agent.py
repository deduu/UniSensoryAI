"""Agent contract — async, context-in / result-out."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.orchestration.models.context import AgentContext
from src.orchestration.models.results import AgentResult


class Agent(ABC):
    """Base class for agents.

    Agents are the unit of work an orchestrator schedules. They receive an
    immutable ``AgentContext`` and return an ``AgentResult``. Timeout
    enforcement is the orchestrator's job, not the agent's, so concrete
    agents stay focused on logic.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Stable identifier (used by Router strategies and logging)."""

    @property
    def description(self) -> str:
        """Optional natural-language description; defaults to empty."""
        return ""

    @abstractmethod
    async def run(self, context: AgentContext) -> AgentResult:
        """Execute the agent.

        Args:
            context: Frozen context describing the user turn.

        Returns:
            A populated ``AgentResult``.
        """

    async def setup(self) -> None:  # noqa: B027 — optional hook
        """Optional one-time setup hook (load caches, warm clients, ...)."""

    async def teardown(self) -> None:  # noqa: B027 — optional hook
        """Optional cleanup hook."""
