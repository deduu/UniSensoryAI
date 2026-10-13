"""Optional adapters without eager imports of local ML implementations."""

from .chat_adapter import ChatGenerationProvider
from .legacy_vision import LegacyVisionGenerationProvider
from .openai_compatible import OpenAICompatibleGenerationProvider

__all__ = [
    "ChatGenerationProvider",
    "LegacyVisionGenerationProvider",
    "OpenAICompatibleGenerationProvider",
]
