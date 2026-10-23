"""Reviewed document drafts are independent, immutable, tenant-scoped snapshots."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from src.paper.contracts import AgreementActor
from src.paper.drafts.content import DocumentDraftContent
from src.paper.drafts.create_request import CreateDocumentDraftRequest
from src.paper.drafts.repository import BaseDocumentDraftRepository
from src.paper.drafts.revise_request import ReviseDocumentDraftRequest
from src.paper.drafts.version import DocumentDraftVersion
from src.paper.errors import AgreementMasterError
from src.services.paper_document_drafts import DocumentDraftService


def _request(*, reviewed: bool = False) -> CreateDocumentDraftRequest:
    return CreateDocumentDraftRequest.model_validate(
        {
            "role": "rent_invoice",
            "document": {
                "source_document_id": "original-pdf",
                "fields": {"invoice_number": "INV-1", "total": "885000000.00"},
                "evidence": [
                    {"field_path": "/total", "source_ids": ["page-1"], "quote": "885,000,000.00"}
                ],
                "warnings": [{"code": "missing_period", "message": "Period not found."}],
            },
            "reviewed": reviewed,
            "reason": "Reviewed against the PDF",
        }
    )


def _version(*, tenant: str = "tenant-a", number: int = 1) -> DocumentDraftVersion:
    return DocumentDraftVersion(
        draft_id="draft-1",
        tenant_id=tenant,
        version_number=number,
        role="rent_invoice",
        document=_request().document,
        status="draft",
        created_by="reviewer",
        created_at=datetime.now(timezone.utc),
        reason="Reviewed against the PDF",
    )


@pytest.mark.parametrize(
    "role", ["rent_invoice", "tax_invoice", "utility_statement", "supporting_document"]
)
def test_all_document_roles_allow_incomplete_fields_without_master_identity(role: str) -> None:
    content = DocumentDraftContent.model_validate(
        {"role": role, "document": {"source_document_id": "source", "fields": {}}}
    )
    assert content.document.source_document_id == "source"


def test_role_mismatch_and_forged_review_provenance_are_rejected() -> None:
    data = _request().model_dump(mode="json")
    data["role"] = "tax_invoice"
    data["document"]["fields"]["withholding_amount"] = "10"
    with pytest.raises(ValidationError):
        CreateDocumentDraftRequest.model_validate(data)
    with pytest.raises(ValidationError):
        CreateDocumentDraftRequest.model_validate(
            {**_request().model_dump(), "reviewed_by": "admin"}
        )


def test_reviewed_snapshot_requires_aware_consistent_server_provenance() -> None:
    data = _version().model_dump()
    with pytest.raises(ValidationError):
        DocumentDraftVersion.model_validate({**data, "status": "reviewed"})
    with pytest.raises(ValidationError):
        DocumentDraftVersion.model_validate({**data, "created_at": datetime(2026, 1, 1)})


@pytest.mark.asyncio
async def test_review_does_not_require_accounting_authority_and_preserves_source_payload() -> None:
    repository = AsyncMock(spec=BaseDocumentDraftRepository)
    repository.create.return_value = _version()
    actor = AgreementActor(tenant_id="tenant-a", user_id="reviewer", can_approve=False)
    result = await DocumentDraftService(repository).create(actor=actor, request=_request())
    assert result.document.evidence == _request().document.evidence
    assert result.document.warnings == _request().document.warnings
    assert repository.create.await_args.kwargs["actor"] == actor
    assert repository.create.await_args.kwargs["request"].reviewed is False


@pytest.mark.asyncio
async def test_exact_read_rejects_wrong_tenant_or_version_from_repository() -> None:
    repository = AsyncMock(spec=BaseDocumentDraftRepository)
    actor = AgreementActor(tenant_id="tenant-a", user_id="reviewer")
    service = DocumentDraftService(repository)
    for result in (_version(tenant="tenant-b"), _version(number=2), None):
        repository.get_version.return_value = result
        with pytest.raises(AgreementMasterError) as caught:
            await service.get_version(actor=actor, draft_id="draft-1", version_number=1)
        assert caught.value.code == "not_found"


@pytest.mark.asyncio
async def test_changed_role_is_rejected_before_repository_append() -> None:
    repository = AsyncMock(spec=BaseDocumentDraftRepository)
    repository.get_version.return_value = _version()
    request = ReviseDocumentDraftRequest.model_validate(
        {
            "expected_version": 1,
            "role": "tax_invoice",
            "document": {"source_document_id": "source", "fields": {}},
            "reason": "Correct",
        }
    )
    with pytest.raises(AgreementMasterError) as caught:
        await DocumentDraftService(repository).revise(
            actor=AgreementActor(tenant_id="tenant-a", user_id="reviewer"),
            draft_id="draft-1",
            request=request,
        )
    assert caught.value.code == "conflict"
    repository.append.assert_not_awaited()


@pytest.mark.asyncio
async def test_storage_timeout_is_sanitized() -> None:
    repository = AsyncMock(spec=BaseDocumentDraftRepository)
    repository.get_version.side_effect = TimeoutError("private connection")
    with pytest.raises(AgreementMasterError) as caught:
        await DocumentDraftService(repository).get_version(
            actor=AgreementActor(tenant_id="tenant-a", user_id="reviewer"),
            draft_id="draft-1",
            version_number=1,
        )
    assert caught.value.code == "timeout"
    assert "private" not in str(caught.value)
