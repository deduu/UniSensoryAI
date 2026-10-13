"""Async generation provider contract."""

from abc import ABC, abstractmethod

from src.extraction.contracts import ModelDescriptor, ModelRequest, ModelResponse


class BaseGenerationProvider(ABC):
    """Narrow generation port, independent of model SDKs and task schemas."""

    @property
    @abstractmethod
    def descriptor(self) -> ModelDescriptor:
        """Return configured model features and limits."""
        ...

    @abstractmethod
    async def complete(self, request: ModelRequest) -> ModelResponse:
        """Generate a normalized response or raise a typed failure."""
        ...

    async def aclose(self) -> None:
        """Release owned resources; injected clients remain host-owned."""
