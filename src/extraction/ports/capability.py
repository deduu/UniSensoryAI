"""Independent typed capability boundary."""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from pydantic import BaseModel

InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)


class BaseCapability(ABC, Generic[InputT, OutputT]):
    """One async operation whose dependencies are supplied by its constructor."""

    @abstractmethod
    async def run(self, data: InputT) -> OutputT:
        """Return a new validated output without mutating shared input."""
        ...
