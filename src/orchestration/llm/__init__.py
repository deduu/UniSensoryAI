"""LLM provider abstraction.

Defines a thin, async-only API every concrete provider satisfies:
``complete`` for one-shot responses. Streaming is intentionally deferred
to a follow-up; the chat endpoint currently wraps full responses in
OpenAI-compatible SSE so the frontend keeps working.
"""

from src.orchestration.llm.base import LLMMessage, LLMProvider, LLMResponse
from src.orchestration.llm.mock import MockLLMProvider
from src.orchestration.llm.openai_compat import OpenAICompatibleClient

__all__ = [
    "LLMMessage",
    "LLMProvider",
    "LLMResponse",
    "MockLLMProvider",
    "OpenAICompatibleClient",
]
