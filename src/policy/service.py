"""Business service for policy review orchestration."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models.document import Document
from src.db.models.ingestion import IngestionJob, IngestionStatus
from src.services.exceptions import NotFoundException

from .agents import (
    DatabasePolicyReferenceAgent,
    LLMPolicyConflictAgent,
    TrustedSourcePolicyReferenceAgent,
    UploadedPolicyConsistencyAgent,
    WebSearchPolicyReferenceAgent,
)
from .models import PolicyClause, PolicyReviewContext, PolicyReviewRequest, PolicyReviewResult
from .orchestrator import ParallelPolicyReviewOrchestrator
from .text_utils import split_clauses
from .web_search import WebSearchTool


POLICY_REVIEW_CHUNK_TYPE = "policy_review_result"


class PolicyReviewService:
    """Coordinates policy review for a completed ingestion job."""

    def __init__(
        self,
        db: AsyncSession,
        *,
        web_search_tool: WebSearchTool | None = None,
    ) -> None:
        self.db = db
        self._web_search_tool = web_search_tool or WebSearchTool()

    async def review_job(
        self,
        job_id: str,
        request: PolicyReviewRequest,
    ) -> PolicyReviewResult:
        """Review the parsed document produced by an ingestion job."""
        job = await self._get_completed_job(job_id)
        if not job.documents:
            raise ValueError("Job has no parsed documents to review.")

        policy_doc = job.documents[0]
        policy_text = policy_doc.content_text or ""
        if not policy_text.strip():
            raise ValueError("Parsed document has no text content to review.")

        reference_clauses: list[PolicyClause] = []
        if request.include_database and request.max_reference_documents > 0:
            reference_clauses = await self._load_reference_clauses(
                exclude_document_id=policy_doc.id,
                limit=request.max_reference_documents,
            )

        context = PolicyReviewContext(
            job_id=job.id,
            policy_document_id=policy_doc.id,
            policy_filename=policy_doc.filename,
            policy_text=policy_text,
            reference_documents=reference_clauses,
            include_web_search=request.include_web_search,
            include_trusted_sources=request.include_trusted_sources,
            focus=request.focus,
        )
        orchestrator = ParallelPolicyReviewOrchestrator(
            agents=[
                UploadedPolicyConsistencyAgent(),
                DatabasePolicyReferenceAgent(),
                TrustedSourcePolicyReferenceAgent(search_tool=self._web_search_tool),
                WebSearchPolicyReferenceAgent(search_tool=self._web_search_tool),
                LLMPolicyConflictAgent(),
            ],
            timeout_seconds=60.0,
        )
        result = await orchestrator.run(context)
        await self._persist_review(policy_doc, result)
        return result

    async def get_saved_review(self, job_id: str) -> PolicyReviewResult | None:
        """Return the latest persisted policy review for a completed job, if any."""
        job = await self._get_completed_job(job_id)
        if not job.documents:
            return None

        return self._extract_review(job.documents[0])

    async def _get_completed_job(self, job_id: str) -> IngestionJob:
        stmt = (
            select(IngestionJob)
            .options(selectinload(IngestionJob.documents))
            .where(IngestionJob.id == job_id)
        )
        result = await self.db.execute(stmt)
        job = result.scalar_one_or_none()
        if job is None:
            raise NotFoundException("IngestionJob", job_id)
        if job.status != IngestionStatus.COMPLETED:
            raise ValueError(f"Only completed jobs can be reviewed. Current status: {job.status.value}")
        return job

    async def _load_reference_clauses(
        self,
        *,
        exclude_document_id: str,
        limit: int,
    ) -> list[PolicyClause]:
        stmt = (
            select(Document)
            .where(Document.id != exclude_document_id)
            .where(Document.content_text.is_not(None))
            .order_by(Document.created_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        documents = result.scalars().all()

        references: list[PolicyClause] = []
        for document in documents:
            for clause in split_clauses(document.content_text or "")[:20]:
                references.append(
                    PolicyClause(
                        text=clause,
                        source="database",
                        document_id=document.id,
                        filename=document.filename,
                    )
                )
        return references

    async def _persist_review(self, document: Document, result: PolicyReviewResult) -> None:
        existing_chunks = [
            chunk
            for chunk in (document.content_chunks or [])
            if not isinstance(chunk, dict) or chunk.get("type") != POLICY_REVIEW_CHUNK_TYPE
        ]
        document.content_chunks = [
            *existing_chunks,
            {
                "type": POLICY_REVIEW_CHUNK_TYPE,
                "result": result.model_dump(),
            },
        ]
        await self.db.commit()

    @staticmethod
    def _extract_review(document: Document) -> PolicyReviewResult | None:
        for chunk in reversed(document.content_chunks or []):
            if not isinstance(chunk, dict):
                continue
            if chunk.get("type") != POLICY_REVIEW_CHUNK_TYPE:
                continue
            result = chunk.get("result")
            if not result:
                return None
            return PolicyReviewResult.model_validate(result)
        return None
