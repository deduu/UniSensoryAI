"""Tool contract — stateless, schema-validated, async function."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from src.orchestration.models.context import ToolInput
from src.orchestration.models.results import ToolResult


class Tool(ABC):
    """Base class for tools an agent may invoke.

    Tools are stateless: they receive a ``ToolInput`` and return a
    ``ToolResult``. State (cached clients, rate limiters, circuit breakers)
    belongs to the tool *instance*, but is wired in at construction — no
    request-scoped state.

    Implementations must expose:

    - ``name``: stable id used to route ``ToolInput.tool_name`` and to
      describe the tool to function-calling LLMs.
    - ``description``: short natural-language summary; the LLM uses it to
      decide when to call the tool.
    - ``input_schema``: JSON Schema document describing ``parameters``.
    - ``execute``: the async work.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Stable identifier for routing and function-calling exposure."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Natural-language description used by tool-selection logic."""

    @property
    @abstractmethod
    def input_schema(self) -> dict[str, Any]:
        """JSON Schema for the ``parameters`` field of ``ToolInput``."""

    @abstractmethod
    async def execute(self, tool_input: ToolInput) -> ToolResult:
        """Run the tool.

        Args:
            tool_input: Validated payload conforming to ``input_schema``.

        Returns:
            The tool's result. Implementations should populate
            ``duration_ms`` and any provider-specific ``metadata``.
        """

    async def validate_input(self, raw: dict[str, Any]) -> ToolInput:
        """Build a ``ToolInput`` from raw parameters.

        Default behaviour is a passthrough; override to perform custom
        validation beyond the JSON Schema (e.g., cross-field checks).
        """
        return ToolInput(tool_name=self.name, parameters=raw)
