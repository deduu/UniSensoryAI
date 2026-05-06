"""Type-based document router — dispatches documents to agents by DocumentType."""

import logging
from typing import List, Tuple

from src.core.base import BaseAgent, BaseRouter
from src.core.document import Document

logger = logging.getLogger(__name__)


class NoAgentFoundError(Exception):
    """Raised when no registered agent can handle a document."""

    def __init__(self, document_type: str) -> None:
        self.document_type = document_type
        super().__init__(f"No agent found for document type: {document_type}")


class TypeRouter(BaseRouter):
    """Routes documents to the highest-priority agent that can handle them.

    Agents are registered with a priority value. When routing, the router
    filters agents by ``can_handle(document)`` and selects the one with the
    highest priority.

    Example::

        router = TypeRouter()
        router.register_agent(PDFAgent(), priority=10)
        router.register_agent(ImageAgent(), priority=10)
        agent = await router.route(document)
    """

    def __init__(self) -> None:
        self._agents: List[Tuple[BaseAgent, int]] = []

    async def route(self, document: Document) -> BaseAgent:
        """Select the best agent for a document.

        Args:
            document: The document to route.

        Returns:
            The highest-priority agent that can handle this document.

        Raises:
            NoAgentFoundError: If no registered agent can handle the document.
        """
        candidates = [
            (agent, priority)
            for agent, priority in self._agents
            if agent.can_handle(document)
        ]

        if not candidates:
            raise NoAgentFoundError(str(document.document_type))

        # Sort by priority descending, return highest
        best_agent = sorted(candidates, key=lambda x: x[1], reverse=True)[0][0]
        logger.info(
            "Router selected agent '%s' for document type '%s'",
            best_agent.name,
            document.document_type,
        )
        return best_agent

    def register_agent(self, agent: BaseAgent, priority: int = 0) -> None:
        """Register an agent with a priority value.

        Args:
            agent: Agent instance to register.
            priority: Higher values = higher priority. Default 0.
        """
        self._agents.append((agent, priority))
        logger.info(
            "Registered agent '%s' with priority %d",
            agent.name,
            priority,
        )

    @property
    def registered_agents(self) -> List[Tuple[BaseAgent, int]]:
        """Return list of (agent, priority) tuples for inspection."""
        return list(self._agents)
