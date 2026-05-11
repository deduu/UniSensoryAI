"""Composite chat agent implementing hybrid routing.

Routes each user turn through one of three paths chosen by
``QueryAnalyzerAgent``:

- ``direct``    → ``DirectAnswererAgent``.
- ``search``    → ``WebResearcherAgent`` → ``SynthesizerAgent``. Falls back
                  to the direct path if the researcher finds no sources, so
                  users get *some* answer rather than an empty synthesis.
- ``ambiguous`` → ``DirectAnswererAgent`` with ``web_search`` exposed as an
                  OpenAI function-calling tool, letting the LLM decide
                  whether to invoke search.

From the outer orchestrator's perspective this is a single agent. The
composite owns its internal coordination so chat callers only need a
``SingleAgentStrategy`` wrapper.
"""

from __future__ import annotations

import logging
from typing import Any

from src.orchestration.interfaces.agent import Agent
from src.orchestration.models.context import AgentContext
from src.orchestration.models.results import AgentResult

logger = logging.getLogger(__name__)

_WEB_SEARCH_TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "Search the public web for recent or factual information. "
            "Use this when the answer depends on current events, fresh "
            "documentation, or facts outside the model's training data."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Free-text search query.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Max results to return.",
                    "minimum": 1,
                    "maximum": 10,
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    },
}


class ChatPipelineAgent(Agent):
    """Hybrid analyzer → (direct | research+synthesize | fn-call) router."""

    def __init__(
        self,
        *,
        analyzer: Agent,
        direct_answerer: Agent,
        web_researcher: Agent,
        synthesizer: Agent,
        ambiguous_answerer: Agent | None = None,
    ) -> None:
        self._analyzer = analyzer
        self._direct = direct_answerer
        self._researcher = web_researcher
        self._synth = synthesizer
        # In ambiguous mode we want the answerer to see ``web_search`` as
        # an exposed tool. The default ``DirectAnswererAgent`` ignores
        # tools (no tool-call execution loop yet); callers can inject a
        # specialised agent here when they wire one up.
        self._ambiguous_answerer = ambiguous_answerer or direct_answerer

    @property
    def name(self) -> str:
        return "chat_pipeline"

    @property
    def description(self) -> str:
        return "Hybrid-routed chat pipeline: analyze, then answer or research."

    async def run(self, context: AgentContext) -> AgentResult:
        analysis = await self._analyzer.run(context)
        query_type = analysis.metadata.get("query_type", "ambiguous")
        refined_queries = analysis.metadata.get("refined_queries") or [context.user_message]
        token_usage = dict(analysis.token_usage)
        base_metadata: dict[str, Any] = {
            "query_type": query_type,
            "refined_queries": refined_queries,
        }

        if query_type == "direct":
            answer = await self._direct.run(context)
            return self._build_result(
                response=answer.response,
                metadata={
                    **base_metadata,
                    "citations": [],
                    "sources": [],
                    "finish_reason": answer.metadata.get("finish_reason", ""),
                },
                token_usage=self._add_tokens(token_usage, answer.token_usage),
            )

        if query_type == "search":
            research_ctx = context.model_copy(
                update={
                    "metadata": {
                        **context.metadata,
                        "refined_queries": refined_queries,
                    }
                }
            )
            research = await self._researcher.run(research_ctx)
            sources = list(research.metadata.get("sources") or [])

            if not sources:
                logger.info(
                    "ChatPipeline: research returned no sources; falling back to direct"
                )
                answer = await self._direct.run(context)
                return self._build_result(
                    response=answer.response,
                    metadata={
                        **base_metadata,
                        "citations": [],
                        "sources": [],
                        "fell_back_to_direct": True,
                        "finish_reason": answer.metadata.get("finish_reason", ""),
                    },
                    token_usage=self._add_tokens(token_usage, answer.token_usage),
                )

            synth_ctx = research_ctx.model_copy(
                update={
                    "metadata": {
                        **research_ctx.metadata,
                        "sources": sources,
                    }
                }
            )
            synthesis = await self._synth.run(synth_ctx)
            return self._build_result(
                response=synthesis.response,
                metadata={
                    **base_metadata,
                    "citations": synthesis.metadata.get("citations") or [],
                    "sources": sources,
                    "source_count": len(sources),
                },
                token_usage=self._add_tokens(token_usage, synthesis.token_usage),
            )

        # Ambiguous: answerer with web_search exposed as a function tool.
        ambiguous_ctx = context.model_copy(
            update={
                "available_tools": [*context.available_tools, "web_search"],
                "metadata": {
                    **context.metadata,
                    "tools": [_WEB_SEARCH_TOOL_SPEC],
                },
            }
        )
        # Reuse the answerer with tool wiring. The default DirectAnswerer
        # doesn't actually execute tool calls yet — we surface the
        # function spec so a follow-up patch can add a tool loop without
        # changing the pipeline contract.
        answer = await self._invoke_ambiguous_answerer(ambiguous_ctx)
        return self._build_result(
            response=answer.response,
            metadata={
                **base_metadata,
                "citations": [],
                "sources": [],
                "tools_offered": ["web_search"],
                "finish_reason": answer.metadata.get("finish_reason", ""),
            },
            token_usage=self._add_tokens(token_usage, answer.token_usage),
        )

    async def _invoke_ambiguous_answerer(self, ctx: AgentContext) -> AgentResult:
        """Wrap the answerer with a ``tools`` kwarg for one call.

        ``DirectAnswererAgent`` accepts ``tools`` at construction. We don't
        want to mutate the shared default instance, so we delegate via a
        small ad-hoc adapter that constructs the tools list per call.
        """
        from src.chat.agents.direct_answerer import DirectAnswererAgent

        if isinstance(self._ambiguous_answerer, DirectAnswererAgent):
            llm = self._ambiguous_answerer._llm  # noqa: SLF001 — adapter
            answerer = DirectAnswererAgent(
                llm=llm,
                tools=[_WEB_SEARCH_TOOL_SPEC],
            )
            return await answerer.run(ctx)
        return await self._ambiguous_answerer.run(ctx)

    @staticmethod
    def _add_tokens(a: dict[str, int], b: dict[str, int]) -> dict[str, int]:
        out = dict(a)
        for k, v in b.items():
            out[k] = out.get(k, 0) + v
        return out

    def _build_result(
        self,
        *,
        response: str,
        metadata: dict[str, Any],
        token_usage: dict[str, int],
    ) -> AgentResult:
        return AgentResult(
            agent_name=self.name,
            response=response,
            metadata=metadata,
            token_usage=token_usage,
        )
