"""LLM-based semantic policy conflict comparator.

Wraps an Anthropic Claude call: sends a proposed policy plus reference
clauses (DB and/or web) and asks the model to identify conflicts with
explanations and recommendations. Uses prompt caching on the reference
block, which is reused across proposal clauses and across runs.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any

from .models import PolicyClause, PolicyFinding


logger = logging.getLogger(__name__)


@dataclass
class LLMComparatorConfig:
    """Configuration for the LLM-based policy comparator."""

    enabled: bool = True
    provider: str = "anthropic"
    model: str = "claude-opus-4-7"
    api_key: str | None = None
    api_key_env: str = "ANTHROPIC_API_KEY"
    max_tokens: int = 4000
    enable_prompt_cache: bool = True
    max_proposal_chars: int = 8000
    max_reference_chars: int = 12000
    severity_floor: str = "medium"
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_policy_config(cls, policy_config: dict[str, Any]) -> "LLMComparatorConfig":
        section = (policy_config or {}).get("llm") or {}
        api_key_env = section.get("api_key_env", "ANTHROPIC_API_KEY")
        return cls(
            enabled=bool(section.get("enabled", True)),
            provider=str(section.get("provider", "anthropic")),
            model=str(section.get("model", "claude-opus-4-7")),
            api_key=section.get("api_key") or os.getenv(api_key_env),
            api_key_env=api_key_env,
            max_tokens=int(section.get("max_tokens", 4000)),
            enable_prompt_cache=bool(section.get("enable_prompt_cache", True)),
            max_proposal_chars=int(section.get("max_proposal_chars", 8000)),
            max_reference_chars=int(section.get("max_reference_chars", 12000)),
            severity_floor=str(section.get("severity_floor", "medium")),
        )


_SYSTEM_PROMPT = (
    "You are a senior policy and compliance analyst. You compare a proposed "
    "policy document against a set of existing policy clauses (from the "
    "company database and/or trusted external sources) and identify "
    "conflicts.\n\n"
    "A conflict exists when the proposed clause and a reference clause:\n"
    "- contradict each other on what is allowed, required, or prohibited;\n"
    "- weaken or relax a control the reference establishes;\n"
    "- expand permission beyond what the reference allows; or\n"
    "- create a numerical, scope, or jurisdictional inconsistency.\n\n"
    "Return only substantive conflicts. Do not invent text. When you cite a "
    "clause, copy the wording verbatim from what was provided. If no real "
    "conflicts exist, return an empty findings list rather than inventing one."
)


_RESPONSE_INSTRUCTION = (
    "Respond with a single JSON object and nothing else. Schema:\n"
    "{\n"
    '  "findings": [\n'
    "    {\n"
    '      "title": "<short title>",\n'
    '      "description": "<2-4 sentence explanation of the conflict>",\n'
    '      "severity": "high" | "medium" | "low",\n'
    '      "proposal_clause": "<verbatim clause from the proposal>",\n'
    '      "reference_clause": "<verbatim clause from the reference>",\n'
    '      "reference_source": "database" | "trusted_source" | "web_search",\n'
    '      "reference_filename": "<filename or source name>",\n'
    '      "reference_location": "<URL if applicable, else null>",\n'
    '      "recommendation": "<concrete action to resolve>",\n'
    '      "confidence": <number between 0 and 1>\n'
    "    }\n"
    "  ]\n"
    "}\n"
    "Do not wrap the JSON in markdown fences. Do not add commentary."
)


class LLMComparator:
    """Async wrapper around the Anthropic Messages API for policy comparison."""

    def __init__(
        self,
        config: LLMComparatorConfig | None = None,
        client: Any | None = None,
    ) -> None:
        self.config = config or LLMComparatorConfig()
        self._client = client

    @property
    def is_configured(self) -> bool:
        return bool(self.config.enabled and self.config.api_key)

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            from anthropic import AsyncAnthropic
        except ImportError as exc:
            raise RuntimeError(
                "anthropic package is required for LLMComparator. "
                "Install it with `pip install anthropic`."
            ) from exc
        self._client = AsyncAnthropic(api_key=self.config.api_key)
        return self._client

    async def compare(
        self,
        *,
        proposal_text: str,
        reference_clauses: list[PolicyClause],
        proposal_document_id: str,
        proposal_filename: str,
        focus: str | None = None,
    ) -> list[PolicyFinding]:
        """Send proposal + references to Claude and parse the structured findings."""
        if not self.is_configured:
            return []
        if not proposal_text.strip() or not reference_clauses:
            return []

        client = self._get_client()
        proposal_block = self._truncate(proposal_text, self.config.max_proposal_chars)
        reference_block = self._render_references(reference_clauses)

        focus_line = f"Focus area: {focus.strip()}\n\n" if focus else ""
        user_blocks = [
            {
                "type": "text",
                "text": (
                    "EXISTING REFERENCE POLICIES (cite these verbatim when "
                    "describing a conflict):\n\n" + reference_block
                ),
            }
        ]
        if self.config.enable_prompt_cache:
            user_blocks[0]["cache_control"] = {"type": "ephemeral"}
        user_blocks.append(
            {
                "type": "text",
                "text": (
                    f"{focus_line}PROPOSED POLICY DOCUMENT (filename: "
                    f"{proposal_filename}):\n\n{proposal_block}\n\n"
                    + _RESPONSE_INSTRUCTION
                ),
            }
        )

        request_kwargs: dict[str, Any] = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "system": _SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": user_blocks}],
        }
        if self.config.model.startswith("claude-opus-4-7") or self.config.model.startswith(
            "claude-opus-4-6"
        ) or self.config.model.startswith("claude-sonnet-4-6"):
            request_kwargs["thinking"] = {"type": "adaptive"}

        response = await client.messages.create(**request_kwargs)
        raw_text = self._extract_text(response)
        usage = getattr(response, "usage", None)
        if usage is not None:
            logger.info(
                "llm_comparator usage cache_read=%s cache_create=%s input=%s output=%s",
                getattr(usage, "cache_read_input_tokens", 0),
                getattr(usage, "cache_creation_input_tokens", 0),
                getattr(usage, "input_tokens", 0),
                getattr(usage, "output_tokens", 0),
            )

        return self._parse_findings(
            raw_text,
            reference_clauses=reference_clauses,
            proposal_document_id=proposal_document_id,
            proposal_filename=proposal_filename,
        )

    @staticmethod
    def _truncate(text: str, limit: int) -> str:
        if limit <= 0 or len(text) <= limit:
            return text
        return text[:limit] + "\n…[truncated]"

    def _render_references(self, references: list[PolicyClause]) -> str:
        rendered: list[str] = []
        used = 0
        for index, clause in enumerate(references, start=1):
            label_parts = [f"[{index}]"]
            if clause.filename:
                label_parts.append(f"source={clause.filename}")
            if clause.source:
                label_parts.append(f"channel={clause.source}")
            if clause.location:
                label_parts.append(f"url={clause.location}")
            header = " ".join(label_parts)
            entry = f"{header}\n{clause.text.strip()}\n"
            if used + len(entry) > self.config.max_reference_chars and rendered:
                break
            rendered.append(entry)
            used += len(entry)
        return "\n".join(rendered)

    @staticmethod
    def _extract_text(response: Any) -> str:
        content = getattr(response, "content", None) or []
        for block in content:
            if getattr(block, "type", None) == "text":
                return getattr(block, "text", "") or ""
        return ""

    def _parse_findings(
        self,
        raw_text: str,
        *,
        reference_clauses: list[PolicyClause],
        proposal_document_id: str,
        proposal_filename: str,
    ) -> list[PolicyFinding]:
        if not raw_text.strip():
            return []
        payload = self._extract_json_object(raw_text)
        if payload is None:
            logger.warning("LLM comparator returned non-JSON payload; skipping.")
            return []

        items = payload.get("findings") or []
        if not isinstance(items, list):
            logger.warning("LLM comparator findings field was not a list.")
            return []

        reference_lookup = {clause.text.strip(): clause for clause in reference_clauses}
        findings: list[PolicyFinding] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            try:
                finding = self._build_finding(
                    item,
                    reference_lookup=reference_lookup,
                    proposal_document_id=proposal_document_id,
                    proposal_filename=proposal_filename,
                )
            except Exception as exc:  # noqa: BLE001 - defensive parse
                logger.warning("Skipping malformed LLM finding: %s", exc)
                continue
            if finding is not None:
                findings.append(finding)
        return findings

    @staticmethod
    def _extract_json_object(text: str) -> dict[str, Any] | None:
        text = text.strip()
        if text.startswith("```"):
            fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
            if fenced:
                text = fenced.group(1)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None

    def _build_finding(
        self,
        item: dict[str, Any],
        *,
        reference_lookup: dict[str, PolicyClause],
        proposal_document_id: str,
        proposal_filename: str,
    ) -> PolicyFinding | None:
        title = str(item.get("title") or "Potential policy conflict").strip()
        description = str(item.get("description") or "").strip()
        if not description:
            return None

        severity = str(item.get("severity") or "medium").lower()
        if severity not in {"high", "medium", "low"}:
            severity = "medium"

        proposal_clause_text = str(item.get("proposal_clause") or "").strip()
        reference_clause_text = str(item.get("reference_clause") or "").strip()
        reference_filename = item.get("reference_filename") or ""
        reference_location = item.get("reference_location") or None
        reference_source_raw = str(item.get("reference_source") or "database").lower()
        if reference_source_raw not in {"database", "trusted_source", "web_search"}:
            reference_source_raw = "database"

        clauses: list[PolicyClause] = []
        if proposal_clause_text:
            clauses.append(
                PolicyClause(
                    text=proposal_clause_text,
                    source="uploaded_document",
                    document_id=proposal_document_id,
                    filename=proposal_filename,
                )
            )
        if reference_clause_text:
            existing = reference_lookup.get(reference_clause_text)
            if existing is not None:
                clauses.append(existing)
            else:
                clauses.append(
                    PolicyClause(
                        text=reference_clause_text,
                        source=reference_source_raw,  # type: ignore[arg-type]
                        filename=reference_filename or None,
                        location=reference_location,
                    )
                )

        confidence_raw = item.get("confidence")
        try:
            confidence = float(confidence_raw) if confidence_raw is not None else 0.7
        except (TypeError, ValueError):
            confidence = 0.7
        confidence = max(0.0, min(1.0, confidence))

        return PolicyFinding(
            title=title,
            description=description,
            severity=severity,  # type: ignore[arg-type]
            source="synthesis",
            clauses=clauses,
            recommendation=(item.get("recommendation") or None),
            confidence=confidence,
            metadata={
                "conflict_reason": description,
                "llm_generated": True,
                "reference_source_kind": reference_source_raw,
            },
        )
