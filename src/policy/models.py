"""Typed models for parallel policy review orchestration."""

from __future__ import annotations

from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field


Severity = Literal["low", "medium", "high"]
EvidenceSource = Literal["uploaded_document", "database", "web_search", "trusted_source", "synthesis"]


class PolicyReviewRequest(BaseModel):
    """Request body for reviewing a parsed policy document."""

    include_database: bool = True
    include_web_search: bool = False
    include_trusted_sources: bool = True
    max_reference_documents: int = Field(default=10, ge=0, le=50)
    focus: str | None = None


class PolicyClause(BaseModel):
    """A policy clause or sentence selected for review."""

    text: str
    source: EvidenceSource
    document_id: str | None = None
    filename: str | None = None
    location: str | None = None


class WebSearchResult(BaseModel):
    """One web search result returned by the search tool."""

    title: str
    url: str
    snippet: str = ""
    provider: str = "duckduckgo"


class PolicyFinding(BaseModel):
    """A possible contradiction or interference found by a review agent."""

    title: str
    description: str
    severity: Severity = "medium"
    source: EvidenceSource
    clauses: list[PolicyClause] = Field(default_factory=list)
    recommendation: str | None = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PolicyReviewContext(BaseModel):
    """Context passed to every policy review agent."""

    job_id: str
    policy_document_id: str
    policy_filename: str
    policy_text: str
    reference_documents: list[PolicyClause] = Field(default_factory=list)
    include_web_search: bool = False
    include_trusted_sources: bool = True
    focus: str | None = None


class PolicyAgentResult(BaseModel):
    """Result returned by one specialized policy review agent."""

    agent_name: str
    findings: list[PolicyFinding] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PolicyReviewResult(BaseModel):
    """Final orchestration result returned to API clients."""

    job_id: str
    document_id: str
    filename: str
    findings: list[PolicyFinding] = Field(default_factory=list)
    agent_results: list[PolicyAgentResult] = Field(default_factory=list)
    summary: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class BasePolicyReviewAgent(Protocol):
    """Protocol implemented by specialized policy review agents."""

    @property
    def name(self) -> str:
        """Unique agent name."""
        ...

    async def review(self, context: PolicyReviewContext) -> PolicyAgentResult:
        """Review the policy and return findings."""
        ...
