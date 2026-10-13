"""Model routing boundary used by capabilities."""

from abc import ABC, abstractmethod

from src.extraction.contracts import ModelDescriptor, ModelRequest, ModelResponse


class BaseModelGateway(ABC):
    """Logical-profile generation with compatibility and resource checks."""

    @abstractmethod
    def describe(self, profile: str) -> ModelDescriptor:
        """Describe a configured profile without loading a model."""
        ...

    @abstractmethod
    async def generate(self, profile: str, request: ModelRequest) -> ModelResponse:
        """Perform a bounded model call."""
        ...
