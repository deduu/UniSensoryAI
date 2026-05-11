"""Grounded-synthesis agent: turn researched sources into a cited answer."""

from __future__ import annotations

from typing import Any

from src.orchestration.interfaces.agent import Agent
from src.orchestration.llm.base import LLMMessage, LLMProvider
from src.orchestration.models.context import AgentContext
from src.orchestration.models.results import AgentResult

_SYSTEM_PROMPT = (
    "You are a research assistant. Answer the user's question using ONLY "
    "the numbered sources below. Cite every factual statement with the "
    "matching number in square brackets like [1], [2]. Combine multiple "
    "sources when relevant. If the sources don't contain the answer, say "
    "so plainly — don't guess.\n\n"
    "Format the answer as concise prose. No headings, no bulleted lists "
    "unless the user asked for one. Keep it under ~250 words."
)

_NO_SOURCES_INSTRUCTION = (
    "You attempted a web search and found no usable sources. Tell the user "
    "you couldn't find sources for their question. Suggest 1-2 ways they "
    "might rephrase or provide context. Do not invent facts."
)


class SynthesizerAgent(Agent):
    """Synthesize a final answer grounded on researched sources.

    Reads ``context.metadata["sources"]`` (the list produced by
    ``WebResearcherAgent``). Each source is rendered as ``[N] title — url``
    followed by the fetched body in the prompt, and the LLM is instructed
    to cite ``[N]`` for every claim. The agent's ``citations`` metadata is
    a parallel list of ``{n, title, url}`` for the frontend.
    """

    def __init__(
        self,
        *,
        llm: LLMProvider,
        temperature: float = 0.3,
        max_body_chars_per_source: int = 4_000,
    ) -> None:
        self._llm = llm
        self._temperature = temperature
        self._max_body_chars = max_body_chars_per_source

    @property
    def name(self) -> str:
        return "synthesizer"

    @property
    def description(self) -> str:
        return "Write a grounded, cited answer using researched sources."

    async def run(self, context: AgentContext) -> AgentResult:
        sources = list(context.metadata.get("sources") or [])

        if not sources:
            messages = [
                LLMMessage(role="system", content=_NO_SOURCES_INSTRUCTION),
                LLMMessage(role="user", content=context.user_message),
            ]
            response = await self._llm.complete(messages, temperature=self._temperature)
            return AgentResult(
                agent_name=self.name,
                response=response.content,
                metadata={"citations": [], "source_count": 0},
                token_usage=response.token_usage,
            )

        sources_block = self._format_sources(sources)
        user_block = (
            f"Question: {context.user_message}\n\n"
            f"Numbered sources:\n{sources_block}\n\n"
            "Write the answer with inline [N] citations."
        )
        messages = [
            LLMMessage(role="system", content=_SYSTEM_PROMPT),
            LLMMessage(role="user", content=user_block),
        ]
        response = await self._llm.complete(messages, temperature=self._temperature)

        citations = [
            {"n": i + 1, "title": src.get("title", ""), "url": src.get("url", "")}
            for i, src in enumerate(sources)
        ]
        return AgentResult(
            agent_name=self.name,
            response=response.content,
            metadata={
                "citations": citations,
                "source_count": len(sources),
            },
            token_usage=response.token_usage,
        )

    def _format_sources(self, sources: list[dict[str, Any]]) -> str:
        parts: list[str] = []
        for i, src in enumerate(sources, start=1):
            title = src.get("title") or "(untitled)"
            url = src.get("url") or ""
            body = (src.get("body") or src.get("snippet") or "").strip()
            if len(body) > self._max_body_chars:
                body = body[: self._max_body_chars] + "..."
            parts.append(f"[{i}] {title}\nURL: {url}\n{body}")
        return "\n\n".join(parts)
