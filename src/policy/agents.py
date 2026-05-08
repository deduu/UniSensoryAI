"""Specialized policy review agents."""

from __future__ import annotations

import asyncio

from .llm_comparator import LLMComparator, LLMComparatorConfig
from .models import (
    PolicyAgentResult,
    PolicyClause,
    PolicyFinding,
    PolicyReviewContext,
    WebSearchResult,
)
from .text_utils import (
    keywords_for_query,
    overlap_score,
    policy_stance,
    shared_content_tokens,
    split_clauses,
)
from .web_search import WebSearchTool
from src.utils.config import ConfigLoader


class UploadedPolicyConsistencyAgent:
    """Find contradictions within the newly uploaded policy document."""

    @property
    def name(self) -> str:
        return "uploaded_policy_consistency"

    async def review(self, context: PolicyReviewContext) -> PolicyAgentResult:
        clauses = split_clauses(context.policy_text)
        findings: list[PolicyFinding] = []

        for index, left in enumerate(clauses):
            left_stance = policy_stance(left)
            if left_stance == "neutral":
                continue
            for right in clauses[index + 1 :]:
                right_stance = policy_stance(right)
                if not self._stances_conflict(left_stance, right_stance):
                    continue
                overlap = overlap_score(left, right)
                shared_tokens = shared_content_tokens(left, right)
                if not self._has_meaningful_overlap(overlap, shared_tokens):
                    continue
                findings.append(
                    PolicyFinding(
                        title="Potential internal policy contradiction",
                        description=self._describe_internal_conflict(
                            left_stance=left_stance,
                            right_stance=right_stance,
                            shared_tokens=shared_tokens,
                        ),
                        severity="high" if overlap >= 0.35 else "medium",
                        source="uploaded_document",
                        clauses=[
                            PolicyClause(
                                text=left,
                                source="uploaded_document",
                                document_id=context.policy_document_id,
                                filename=context.policy_filename,
                            ),
                            PolicyClause(
                                text=right,
                                source="uploaded_document",
                                document_id=context.policy_document_id,
                                filename=context.policy_filename,
                            ),
                        ],
                        recommendation=(
                            "Clarify which clause controls, or rewrite one clause so the "
                            "permission, prohibition, and exception hierarchy is explicit."
                        ),
                        confidence=min(0.95, 0.45 + overlap + min(len(shared_tokens), 4) * 0.05),
                        metadata={
                            "conflict_reason": self._describe_internal_conflict(
                                left_stance=left_stance,
                                right_stance=right_stance,
                                shared_tokens=shared_tokens,
                            ),
                            "left_stance": left_stance,
                            "right_stance": right_stance,
                            "overlap_score": overlap,
                            "shared_tokens": sorted(shared_tokens),
                            "shared_token_count": len(shared_tokens),
                        },
                    )
                )

        return PolicyAgentResult(
            agent_name=self.name,
            findings=findings,
            metadata={"clauses_reviewed": len(clauses)},
        )

    @staticmethod
    def _stances_conflict(left: str, right: str) -> bool:
        return {left, right} in ({"allow", "deny"}, {"require", "deny"})

    @staticmethod
    def _has_meaningful_overlap(overlap: float, shared_tokens: set[str]) -> bool:
        return overlap >= 0.1 or len(shared_tokens) >= 3

    @staticmethod
    def _describe_internal_conflict(
        *,
        left_stance: str,
        right_stance: str,
        shared_tokens: set[str],
    ) -> str:
        shared_text = _shared_terms_text(shared_tokens)
        return (
            f"One clause {_stance_phrase(left_stance)}, while another {_stance_phrase(right_stance)}, "
            f"on the same topic ({shared_text})."
        )


class DatabasePolicyReferenceAgent:
    """Compare the uploaded policy against already parsed documents in the database."""

    @property
    def name(self) -> str:
        return "database_policy_reference"

    async def review(self, context: PolicyReviewContext) -> PolicyAgentResult:
        policy_clauses = split_clauses(context.policy_text)
        findings: list[PolicyFinding] = []

        for policy_clause in policy_clauses:
            policy_stance_value = policy_stance(policy_clause)
            if policy_stance_value == "neutral":
                continue
            for reference in context.reference_documents:
                reference_stance = policy_stance(reference.text)
                if not UploadedPolicyConsistencyAgent._stances_conflict(
                    policy_stance_value, reference_stance
                ):
                    continue
                overlap = overlap_score(policy_clause, reference.text)
                shared_tokens = shared_content_tokens(policy_clause, reference.text)
                if not UploadedPolicyConsistencyAgent._has_meaningful_overlap(
                    overlap, shared_tokens
                ):
                    continue
                findings.append(
                    PolicyFinding(
                        title="Potential conflict with existing stored policy",
                        description=_describe_cross_source_conflict(
                            proposal_stance=policy_stance_value,
                            reference_stance=reference_stance,
                            shared_tokens=shared_tokens,
                            reference_label="the stored policy",
                        ),
                        severity="high" if overlap >= 0.32 else "medium",
                        source="database",
                        clauses=[
                            PolicyClause(
                                text=policy_clause,
                                source="uploaded_document",
                                document_id=context.policy_document_id,
                                filename=context.policy_filename,
                            ),
                            reference,
                        ],
                        recommendation=(
                            "Check whether the uploaded policy supersedes the stored policy, "
                            "then add an effective date, scope, or override clause."
                        ),
                        confidence=min(0.9, 0.4 + overlap + min(len(shared_tokens), 4) * 0.05),
                        metadata={
                            "conflict_reason": _describe_cross_source_conflict(
                                proposal_stance=policy_stance_value,
                                reference_stance=reference_stance,
                                shared_tokens=shared_tokens,
                                reference_label="the stored policy",
                            ),
                            "proposal_stance": policy_stance_value,
                            "reference_stance": reference_stance,
                            "overlap_score": overlap,
                            "shared_tokens": sorted(shared_tokens),
                            "shared_token_count": len(shared_tokens),
                        },
                    )
                )

        return PolicyAgentResult(
            agent_name=self.name,
            findings=findings,
            metadata={"reference_clauses_reviewed": len(context.reference_documents)},
        )


class TrustedSourcePolicyReferenceAgent:
    """Compare the uploaded policy against a curated list of trusted policy URLs."""

    def __init__(
        self,
        *,
        search_tool: WebSearchTool | None = None,
        max_sources: int | None = None,
    ) -> None:
        policy_config = ConfigLoader.get_policy_config()
        trusted_config = policy_config.get("trusted_sources", {})
        self._enabled = bool(trusted_config.get("enabled", False))
        self._sources = list(trusted_config.get("sources", []))
        self._max_sources = max_sources or int(
            trusted_config.get("max_sources", max(len(self._sources), 1))
        )
        self._search_tool = search_tool or WebSearchTool()

    @property
    def name(self) -> str:
        return "trusted_source_policy_reference"

    async def review(self, context: PolicyReviewContext) -> PolicyAgentResult:
        if not context.include_trusted_sources:
            return PolicyAgentResult(
                agent_name=self.name,
                notes=["Trusted source review was not requested."],
                metadata={"skipped": True},
            )
        if not self._enabled or not self._sources:
            return PolicyAgentResult(
                agent_name=self.name,
                notes=["No trusted policy sources are configured."],
                metadata={"skipped": True},
            )

        policy_clauses = [
            clause
            for clause in split_clauses(context.policy_text)
            if policy_stance(clause) != "neutral"
        ]
        if not policy_clauses:
            return PolicyAgentResult(
                agent_name=self.name,
                notes=["No policy clauses were specific enough to compare against trusted sources."],
                metadata={"skipped": True},
            )

        selected_sources = self._select_sources(context.focus)[: self._max_sources]
        fetch_tasks = [
            self._search_tool.fetch_page_text(source["url"])
            for source in selected_sources
        ]
        raw_pages = await asyncio.gather(*fetch_tasks, return_exceptions=True)

        findings: list[PolicyFinding] = []
        notes: list[str] = []
        failed_sources = 0
        seen_pairs: set[tuple[str, str, str]] = set()

        for source, page_result in zip(selected_sources, raw_pages, strict=True):
            if isinstance(page_result, Exception):
                failed_sources += 1
                notes.append(f"Trusted source fetch failed for {source['name']}: {page_result}")
                continue

            source_clauses = [
                clause
                for clause in split_clauses(page_result)[:80]
                if policy_stance(clause) != "neutral"
            ]
            if not source_clauses:
                notes.append(f"No reviewable policy clauses were extracted from {source['name']}.")
                continue

            for policy_clause in policy_clauses:
                proposal_stance = policy_stance(policy_clause)
                for source_clause in source_clauses:
                    reference_stance = policy_stance(source_clause)
                    if not UploadedPolicyConsistencyAgent._stances_conflict(
                        proposal_stance, reference_stance
                    ):
                        continue
                    overlap = overlap_score(policy_clause, source_clause)
                    shared_tokens = shared_content_tokens(policy_clause, source_clause)
                    if overlap < 0.08 and len(shared_tokens) < 2:
                        continue

                    pair_key = (policy_clause, source_clause, source["url"])
                    if pair_key in seen_pairs:
                        continue
                    seen_pairs.add(pair_key)

                    conflict_reason = _describe_cross_source_conflict(
                        proposal_stance=proposal_stance,
                        reference_stance=reference_stance,
                        shared_tokens=shared_tokens,
                        reference_label=source["name"],
                    )
                    findings.append(
                        PolicyFinding(
                            title="Potential conflict with trusted policy source",
                            description=conflict_reason,
                            severity="high" if overlap >= 0.28 or len(shared_tokens) >= 4 else "medium",
                            source="trusted_source",
                            clauses=[
                                PolicyClause(
                                    text=policy_clause,
                                    source="uploaded_document",
                                    document_id=context.policy_document_id,
                                    filename=context.policy_filename,
                                ),
                                PolicyClause(
                                    text=source_clause,
                                    source="trusted_source",
                                    filename=source["name"],
                                    location=source["url"],
                                ),
                            ],
                            recommendation=(
                                "Review whether the proposal intentionally overrides this trusted source. "
                                "If not, narrow scope, add an exception rule, or revise the proposal clause."
                            ),
                            confidence=min(0.92, 0.42 + overlap + min(len(shared_tokens), 4) * 0.05),
                            metadata={
                                "conflict_reason": conflict_reason,
                                "proposal_stance": proposal_stance,
                                "reference_stance": reference_stance,
                                "overlap_score": overlap,
                                "shared_tokens": sorted(shared_tokens),
                                "shared_token_count": len(shared_tokens),
                                "url": source["url"],
                                "title": source["name"],
                                "reference_excerpt_source": "trusted_source_page",
                                "trusted_source": True,
                            },
                        )
                    )

        if not findings and not notes:
            notes.append("Trusted source comparison completed, but no deterministic external conflicts were detected.")

        return PolicyAgentResult(
            agent_name=self.name,
            findings=findings,
            notes=notes,
            metadata={
                "sources_checked": len(selected_sources),
                "failed_sources": failed_sources,
                "configured": True,
                "degraded": failed_sources > 0,
            },
        )

    def _select_sources(self, focus: str | None) -> list[dict[str, object]]:
        if not focus:
            return self._sources

        focus_terms = set(keywords_for_query(focus, max_terms=8))
        ranked_sources: list[tuple[int, dict[str, object]]] = []
        for source in self._sources:
            source_terms = set(keywords_for_query(str(source.get("name", "")), max_terms=8))
            for topic in source.get("topics", []) or []:
                source_terms.update(keywords_for_query(str(topic), max_terms=8))
            score = len(focus_terms & source_terms)
            ranked_sources.append((score, source))

        ranked_sources.sort(key=lambda item: item[0], reverse=True)
        matched = [source for score, source in ranked_sources if score > 0]
        return matched or self._sources


class WebSearchPolicyReferenceAgent:
    """Compare the uploaded policy against public web search results."""

    def __init__(
        self,
        *,
        search_tool: WebSearchTool | None = None,
        max_queries: int | None = None,
        max_results_per_query: int | None = None,
    ) -> None:
        policy_config = ConfigLoader.get_policy_config()
        web_config = policy_config.get("web_search", {})
        self._search_tool = search_tool or WebSearchTool()
        self._max_queries = max_queries or int(web_config.get("max_queries", 4))
        self._max_results_per_query = max_results_per_query or int(
            web_config.get("max_results", 3)
        )

    @property
    def name(self) -> str:
        return "web_search_policy_reference"

    async def review(self, context: PolicyReviewContext) -> PolicyAgentResult:
        if not context.include_web_search:
            return PolicyAgentResult(
                agent_name=self.name,
                notes=["Web search review was not requested."],
                metadata={"skipped": True},
            )

        policy_clauses = [
            clause
            for clause in split_clauses(context.policy_text)
            if policy_stance(clause) != "neutral"
        ][: self._max_queries]
        if not policy_clauses:
            return PolicyAgentResult(
                agent_name=self.name,
                notes=["No policy clauses were specific enough to use for web search review."],
                metadata={"skipped": True},
            )

        query_pairs = [
            (clause, self._build_query(clause, context.focus))
            for clause in policy_clauses
        ]
        raw_results = await asyncio.gather(
            *(
                self._search_tool.search(query, max_results=self._max_results_per_query)
                for _, query in query_pairs
            ),
            return_exceptions=True,
        )

        findings: list[PolicyFinding] = []
        notes: list[str] = []
        results_considered = 0
        failed_queries = 0

        for (policy_clause, query), search_result in zip(query_pairs, raw_results, strict=True):
            if isinstance(search_result, Exception):
                failed_queries += 1
                notes.append(f"Web search failed for query '{query}': {search_result}")
                continue

            results_considered += len(search_result)
            query_findings, query_notes = await self._find_conflicts(
                    context=context,
                    policy_clause=policy_clause,
                    query=query,
                    search_results=search_result,
                )
            findings.extend(query_findings)
            notes.extend(query_notes)

        if not findings and not notes:
            notes.append("Web search completed, but no conflicting public-source snippets were detected.")
        if failed_queries and failed_queries == len(query_pairs):
            notes.append("Public web evidence was unavailable for this run because every web search query failed.")

        return PolicyAgentResult(
            agent_name=self.name,
            findings=findings,
            notes=notes,
            metadata={
                "queries_run": len(query_pairs),
                "results_considered": results_considered,
                "failed_queries": failed_queries,
                "degraded": failed_queries > 0,
                "configured": True,
            },
        )

    @staticmethod
    def _build_query(clause: str, focus: str | None) -> str:
        parts = keywords_for_query(clause, max_terms=8)
        if focus:
            parts.extend(keywords_for_query(focus, max_terms=4))
        parts.extend(["policy", "regulation"])
        return " ".join(parts)

    async def _find_conflicts(
        self,
        *,
        context: PolicyReviewContext,
        policy_clause: str,
        query: str,
        search_results: list[WebSearchResult],
    ) -> tuple[list[PolicyFinding], list[str]]:
        findings: list[PolicyFinding] = []
        notes: list[str] = []
        policy_clause_stance = policy_stance(policy_clause)
        page_text_results = await asyncio.gather(
            *(self._fetch_result_page_text(result.url) for result in search_results),
            return_exceptions=True,
        )

        for result, page_text_result in zip(search_results, page_text_results, strict=True):
            page_text = ""
            if isinstance(page_text_result, Exception):
                notes.append(f"Could not read external source {result.url}: {page_text_result}")
            else:
                page_text = page_text_result

            reference_match = self._best_reference_match(
                policy_clause=policy_clause,
                policy_clause_stance=policy_clause_stance,
                result=result,
                page_text=page_text,
            )
            if reference_match is None:
                continue
            reference_text, reference_stance, overlap, shared_tokens, matched_from_page = (
                reference_match
            )
            reference_label = result.title or "the cited external policy"
            conflict_reason = _describe_cross_source_conflict(
                proposal_stance=policy_clause_stance,
                reference_stance=reference_stance,
                shared_tokens=shared_tokens,
                reference_label=reference_label,
            )

            findings.append(
                PolicyFinding(
                    title="Potential conflict with external policy source",
                    description=conflict_reason,
                    severity="high" if overlap >= 0.3 else "medium",
                    source="web_search",
                    clauses=[
                        PolicyClause(
                            text=policy_clause,
                            source="uploaded_document",
                            document_id=context.policy_document_id,
                            filename=context.policy_filename,
                        ),
                        PolicyClause(
                            text=reference_text,
                            source="web_search",
                            filename=result.title,
                            location=result.url,
                        ),
                    ],
                    recommendation=(
                        "Open the cited source and verify scope, jurisdiction, and effective date "
                        "before treating this as a real contradiction."
                    ),
                    confidence=min(0.8, 0.35 + overlap + min(len(shared_tokens), 3) * 0.05),
                    metadata={
                        "conflict_reason": conflict_reason,
                        "overlap_score": overlap,
                        "proposal_stance": policy_clause_stance,
                        "reference_stance": reference_stance,
                        "shared_tokens": sorted(shared_tokens),
                        "shared_token_count": len(shared_tokens),
                        "reference_excerpt_source": "page_text" if matched_from_page else "search_snippet",
                        "url": result.url,
                        "title": result.title,
                        "query": query,
                    },
                )
            )
        return findings, notes

    async def _fetch_result_page_text(self, url: str) -> str:
        fetch_page_text = getattr(self._search_tool, "fetch_page_text", None)
        if not callable(fetch_page_text):
            return ""
        return await fetch_page_text(url)

    @staticmethod
    def _best_reference_match(
        *,
        policy_clause: str,
        policy_clause_stance: str,
        result: WebSearchResult,
        page_text: str,
    ) -> tuple[str, str, float, set[str], bool] | None:
        candidates: list[tuple[float, str, str, float, set[str], bool]] = []

        def consider_candidate(reference_text: str, *, matched_from_page: bool) -> None:
            reference_stance = policy_stance(reference_text)
            if not UploadedPolicyConsistencyAgent._stances_conflict(
                policy_clause_stance, reference_stance
            ):
                return
            overlap = overlap_score(policy_clause, reference_text)
            shared_tokens = shared_content_tokens(policy_clause, reference_text)
            if overlap < 0.08 and len(shared_tokens) < 2:
                return
            score = overlap + min(len(shared_tokens), 5) * 0.03
            candidates.append(
                (score, reference_text, reference_stance, overlap, shared_tokens, matched_from_page)
            )

        if page_text:
            for clause in split_clauses(page_text)[:80]:
                consider_candidate(clause, matched_from_page=True)

        snippet_text = result.snippet or result.title
        if snippet_text:
            consider_candidate(snippet_text, matched_from_page=False)

        if not candidates:
            return None

        _, reference_text, reference_stance, overlap, shared_tokens, matched_from_page = max(
            candidates, key=lambda item: item[0]
        )
        return reference_text, reference_stance, overlap, shared_tokens, matched_from_page


class LLMPolicyConflictAgent:
    """Use a Claude model to flag semantic conflicts the heuristic agents miss."""

    def __init__(
        self,
        *,
        comparator: LLMComparator | None = None,
    ) -> None:
        if comparator is None:
            try:
                policy_config = ConfigLoader.get_policy_config()
            except FileNotFoundError:
                policy_config = {}
            config = LLMComparatorConfig.from_policy_config(policy_config)
            comparator = LLMComparator(config=config)
        self._comparator = comparator

    @property
    def name(self) -> str:
        return "llm_policy_conflict"

    async def review(self, context: PolicyReviewContext) -> PolicyAgentResult:
        config = self._comparator.config

        if not config.enabled:
            return PolicyAgentResult(
                agent_name=self.name,
                notes=["LLM policy comparator is disabled in policy.yaml."],
                metadata={"skipped": True, "reason": "disabled"},
            )

        if not config.api_key:
            return PolicyAgentResult(
                agent_name=self.name,
                notes=[
                    f"LLM policy comparator skipped: {config.api_key_env} is not set."
                ],
                metadata={"skipped": True, "reason": "missing_api_key"},
            )

        if not context.policy_text or not context.policy_text.strip():
            return PolicyAgentResult(
                agent_name=self.name,
                notes=["No proposal text was available for LLM comparison."],
                metadata={"skipped": True, "reason": "empty_proposal"},
            )

        if not context.reference_documents:
            return PolicyAgentResult(
                agent_name=self.name,
                notes=[
                    "No reference clauses were available for LLM comparison. "
                    "Ingest existing policies first or enable database references."
                ],
                metadata={"skipped": True, "reason": "no_references"},
            )

        try:
            findings = await self._comparator.compare(
                proposal_text=context.policy_text,
                reference_clauses=list(context.reference_documents),
                proposal_document_id=context.policy_document_id,
                proposal_filename=context.policy_filename,
                focus=context.focus,
            )
        except Exception as exc:  # noqa: BLE001 - return as agent error
            return PolicyAgentResult(
                agent_name=self.name,
                notes=[f"LLM policy comparator failed: {exc}"],
                metadata={"error": str(exc)},
            )

        notes: list[str] = []
        if not findings:
            notes.append(
                "LLM comparator found no substantive conflicts against the "
                "available reference clauses."
            )

        return PolicyAgentResult(
            agent_name=self.name,
            findings=findings,
            notes=notes,
            metadata={
                "model": config.model,
                "references_considered": len(context.reference_documents),
                "findings_returned": len(findings),
            },
        )


def _stance_phrase(stance: str) -> str:
    if stance == "allow":
        return "allows the activity"
    if stance == "deny":
        return "restricts or prohibits the activity"
    if stance == "require":
        return "requires the activity or a control around it"
    return "addresses the activity"


def _shared_terms_text(shared_tokens: set[str]) -> str:
    if not shared_tokens:
        return "related subject matter"
    shared_list = sorted(shared_tokens)
    return ", ".join(shared_list[:4])


def _describe_cross_source_conflict(
    *,
    proposal_stance: str,
    reference_stance: str,
    shared_tokens: set[str],
    reference_label: str,
) -> str:
    shared_text = _shared_terms_text(shared_tokens)
    return (
        f"The proposal {_stance_phrase(proposal_stance)}, but {reference_label} "
        f"{_stance_phrase(reference_stance)} on the same topic ({shared_text})."
    )
