"""Tests for policy review service persistence."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.policy.models import PolicyReviewRequest, PolicyReviewResult
from src.policy.service import PolicyReviewService


class FakeOrchestrator:
    """Small orchestrator test double returning a deterministic review."""

    def __init__(self, *args, **kwargs) -> None:
        pass

    async def run(self, context):
        return PolicyReviewResult(
            job_id=context.job_id,
            document_id=context.policy_document_id,
            filename=context.policy_filename,
            summary="Persisted review",
            metadata={"agent_count": 1},
        )


@pytest.mark.asyncio
async def test_review_job_persists_result_without_removing_existing_chunks():
    """Running a review should save the latest result on the reviewed document."""
    db = AsyncMock()
    service = PolicyReviewService(db)
    document = SimpleNamespace(
        id="doc-1",
        filename="policy.pdf",
        content_text="Employees may share data. Employees must not share data.",
        content_chunks=[{"type": "text", "text": "existing chunk"}],
    )
    job = SimpleNamespace(id="job-1", documents=[document])
    service._get_completed_job = AsyncMock(return_value=job)
    service._load_reference_clauses = AsyncMock(return_value=[])

    with patch("src.policy.service.ParallelPolicyReviewOrchestrator", FakeOrchestrator):
        result = await service.review_job("job-1", PolicyReviewRequest())

    assert result.summary == "Persisted review"
    assert document.content_chunks[0] == {"type": "text", "text": "existing chunk"}
    saved = document.content_chunks[1]
    assert saved["type"] == "policy_review_result"
    assert saved["result"]["job_id"] == "job-1"
    assert saved["result"]["document_id"] == "doc-1"
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_saved_review_returns_latest_policy_review_result():
    """Saved policy review results should be reloadable for the UI."""
    db = AsyncMock()
    service = PolicyReviewService(db)
    document = SimpleNamespace(
        id="doc-1",
        filename="policy.pdf",
        content_text="Policy text",
        content_chunks=[
            {"type": "text", "text": "existing chunk"},
            {
                "type": "policy_review_result",
                "result": {
                    "job_id": "job-1",
                    "document_id": "doc-1",
                    "filename": "policy.pdf",
                    "findings": [],
                    "agent_results": [],
                    "summary": "Saved result",
                    "metadata": {},
                },
            },
        ],
    )
    job = SimpleNamespace(id="job-1", documents=[document])
    service._get_completed_job = AsyncMock(return_value=job)

    result = await service.get_saved_review("job-1")

    assert result is not None
    assert result.summary == "Saved result"
