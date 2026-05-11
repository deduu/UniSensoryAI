"""Classify a user turn as direct / search / ambiguous and refine queries.

The analyzer is the first hop in the chat pipeline. Its job is cheap and
deterministic: one LLM call in JSON mode that yields a routing decision
plus a small list of refined search queries when a web search would help.

The output drives ``ChatPipelineAgent``'s hybrid routing:

- "direct"    → answer from the model alone.
- "search"    → research the refined queries, then synthesize.
- "ambiguous" → fall back to function-calling so the LLM can decide.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from src.orchestration.interfaces.agent import Agent
from src.orchestration.llm.base import LLMMessage, LLMProvider
from src.orchestration.models.context import AgentContext
from src.orchestration.models.results import AgentResult

logger = logging.getLogger(__name__)

_VALID_TYPES = {"direct", "search", "ambiguous"}

_SYSTEM_PROMPT = (
    "You are a routing classifier for a chat assistant. For each user "
    "message, decide whether the model can answer directly or whether a "
    "web search is required, then propose refined search queries if a "
    "search is warranted.\n\n"
    "Reply ONLY with a JSON object matching this schema:\n"
    '{"query_type": "direct" | "search" | "ambiguous", '
    '"refined_queries": [string, ...], '
    '"reasoning": string}\n\n'
    "Use \"direct\" for math, definitions, code edits, opinions, and "
    "personal/contextual questions. Use \"search\" for recent news, "
    "live facts, version-specific docs, or anything time-sensitive. "
    "Use \"ambiguous\" only when you genuinely can't tell. Provide 1-3 "
    "refined queries for \"search\", or echo the user's message for "
    "\"direct\" / \"ambiguous\"."
)


class QueryAnalyzerAgent(Agent):
    """Classify the user message and produce refined queries."""

    def __init__(
        self,
        *,
        llm: LLMProvider,
        temperature: float = 0.0,
    ) -> None:
        self._llm = llm
        self._temperature = temperature

    @property
    def name(self) -> str:
        return "query_analyzer"

    @property
    def description(self) -> str:
        return "Classify the user turn and propose refined web queries."

    async def run(self, context: AgentContext) -> AgentResult:
        messages = [
            LLMMessage(role="system", content=_SYSTEM_PROMPT),
            LLMMessage(role="user", content=context.user_message),
        ]
        response = await self._llm.complete(
            messages,
            temperature=self._temperature,
            response_format={"type": "json_object"},
        )

        parsed = self._parse(response.content, fallback_query=context.user_message)

        return AgentResult(
            agent_name=self.name,
            response=parsed["reasoning"],
            metadata={
                "query_type": parsed["query_type"],
                "refined_queries": parsed["refined_queries"],
            },
            token_usage=response.token_usage,
        )

    def _parse(self, raw: str, *, fallback_query: str) -> dict[str, Any]:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("QueryAnalyzer: LLM returned non-JSON; falling back to ambiguous")
            return {
                "query_type": "ambiguous",
                "refined_queries": [fallback_query],
                "reasoning": "Could not parse classifier output.",
            }

        query_type = str(data.get("query_type", "")).strip().lower()
        if query_type not in _VALID_TYPES:
            query_type = "ambiguous"

        refined = data.get("refined_queries") or []
        if not isinstance(refined, list):
            refined = [str(refined)]
        refined = [str(q).strip() for q in refined if str(q).strip()]
        if not refined:
            refined = [fallback_query]

        reasoning = str(data.get("reasoning") or "")
        return {
            "query_type": query_type,
            "refined_queries": refined,
            "reasoning": reasoning,
        }
