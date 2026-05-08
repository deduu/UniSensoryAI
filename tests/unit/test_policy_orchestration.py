"""Tests for parallel policy review orchestration."""

from __future__ import annotations

import asyncio

import pytest

from src.policy.agents import DatabasePolicyReferenceAgent, UploadedPolicyConsistencyAgent
from src.policy.models import (
    PolicyAgentResult,
    PolicyClause,
    PolicyReviewContext,
)
from src.policy.orchestrator import ParallelPolicyReviewOrchestrator


class SlowNoopAgent:
    @property
    def name(self) -> str:
        return "slow_noop"

    async def review(self, context: PolicyReviewContext) -> PolicyAgentResult:
        await asyncio.sleep(0.01)
        return PolicyAgentResult(agent_name=self.name)


class DegradedNoopAgent:
    @property
    def name(self) -> str:
        return "degraded_noop"

    async def review(self, context: PolicyReviewContext) -> PolicyAgentResult:
        return PolicyAgentResult(
            agent_name=self.name,
            notes=["Web coverage unavailable."],
            metadata={"degraded": True},
        )


@pytest.mark.asyncio
async def test_uploaded_policy_consistency_finds_internal_conflict():
    agent = UploadedPolicyConsistencyAgent()
    context = PolicyReviewContext(
        job_id="job-1",
        policy_document_id="doc-1",
        policy_filename="policy.pdf",
        policy_text=(
            "Employees may share customer data with vendors for support. "
            "Employees must not share customer data with vendors."
        ),
    )

    result = await agent.review(context)

    assert result.agent_name == "uploaded_policy_consistency"
    assert len(result.findings) == 1
    assert result.findings[0].source == "uploaded_document"
    assert result.findings[0].severity == "high"


@pytest.mark.asyncio
async def test_uploaded_policy_consistency_flags_sample_policy_conflict_with_lower_overlap():
    agent = UploadedPolicyConsistencyAgent()
    context = PolicyReviewContext(
        job_id="job-1",
        policy_document_id="doc-1",
        policy_filename="policy.pdf",
        policy_text=(
            "Employees may enter public, internal, confidential, and limited student support data "
            "into public generative AI systems when the employee believes the operational benefit "
            "outweighs the residual risk. "
            "Employees must not enter confidential customer, student, employee, or health information "
            "into any external AI service unless that service has been explicitly approved by both ITS and Legal."
        ),
    )

    result = await agent.review(context)

    assert len(result.findings) == 1
    assert result.findings[0].metadata["shared_token_count"] >= 3
    assert "confidential" in result.findings[0].metadata["shared_tokens"]


@pytest.mark.asyncio
async def test_database_agent_compares_uploaded_policy_to_reference_clauses():
    agent = DatabasePolicyReferenceAgent()
    context = PolicyReviewContext(
        job_id="job-1",
        policy_document_id="doc-1",
        policy_filename="new-policy.pdf",
        policy_text="Employees may share customer data with vendors for support.",
        reference_documents=[
            PolicyClause(
                text="Employees must not share customer data with vendors.",
                source="database",
                document_id="doc-old",
                filename="old-policy.pdf",
            )
        ],
    )

    result = await agent.review(context)

    assert len(result.findings) == 1
    assert result.findings[0].source == "database"
    assert result.findings[0].clauses[1].document_id == "doc-old"


@pytest.mark.asyncio
async def test_parallel_orchestrator_runs_agents_and_merges_results():
    context = PolicyReviewContext(
        job_id="job-1",
        policy_document_id="doc-1",
        policy_filename="policy.pdf",
        policy_text=(
            "Employees may share customer data with vendors for support. "
            "Employees must not share customer data with vendors."
        ),
    )
    orchestrator = ParallelPolicyReviewOrchestrator(
        agents=[UploadedPolicyConsistencyAgent(), SlowNoopAgent()]
    )

    result = await orchestrator.run(context)

    assert result.job_id == "job-1"
    assert result.metadata["agent_count"] == 2
    assert len(result.agent_results) == 2
    assert len(result.findings) == 1
    assert "Detected 1" in result.summary


@pytest.mark.asyncio
async def test_parallel_orchestrator_marks_summary_incomplete_when_agents_degrade():
    context = PolicyReviewContext(
        job_id="job-1",
        policy_document_id="doc-1",
        policy_filename="policy.pdf",
        policy_text="Employees may share customer data with vendors for support.",
    )
    orchestrator = ParallelPolicyReviewOrchestrator(agents=[DegradedNoopAgent()])

    result = await orchestrator.run(context)

    assert result.findings == []
    assert "review is incomplete" in result.summary
