"""Pluggable orchestration strategies.

Each strategy implements ``OrchestratorStrategy`` by exposing
``execute(agents, context) -> AgentResult``. Pick a strategy when wiring an
``Orchestrator``; swap it at runtime via the ``strategy`` setter.
"""

from src.orchestration.strategies.parallel import ParallelStrategy
from src.orchestration.strategies.pipeline import PipelineStrategy
from src.orchestration.strategies.router import RouterStrategy
from src.orchestration.strategies.single_agent import SingleAgentStrategy

__all__ = [
    "ParallelStrategy",
    "PipelineStrategy",
    "RouterStrategy",
    "SingleAgentStrategy",
]
