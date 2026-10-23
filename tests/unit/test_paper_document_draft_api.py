"""Document-draft transport keeps trusted review provenance out of client inputs."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI

from src.api.auth import UserContext, get_user_context
from src.api.paper_document_draft_routes import get_document_draft_service, router
from src.api.paper_routes import get_paper_db
from src.paper.drafts.page import DocumentDraftPage
from src.paper.drafts.version import DocumentDraftVersion
from src.paper.errors import AgreementMasterError
from src.services.paper_document_drafts import DocumentDraftService


@pytest.mark.asyncio
async def test_draft_transport_validates_review_intent_and_uses_authenticated_scope() -> None:
    app = FastAPI()
    app.include_router(router)
    service = AsyncMock(spec=DocumentDraftService)
    db = AsyncMock()
    now = datetime.now(timezone.utc)
    record = DocumentDraftVersion.model_validate(
        {
            "draft_id": "draft-1",
            "tenant_id": "tenant-a",
            "version_number": 1,
            "role": "rent_invoice",
            "document": {"source_document_id": "source", "fields": {}},
            "status": "reviewed",
            "created_by": "reviewer",
            "created_at": now,
            "reason": "Checked",
            "reviewed_by": "reviewer",
            "reviewed_at": now,
        }
    )
    service.create.return_value = record
    service.list_latest.return_value = DocumentDraftPage(
        items=(record,), total=1, limit=1, offset=0
    )
    service.get_version.side_effect = AgreementMasterError(
        "not_found", "Document draft version was not found."
    )
    app.dependency_overrides[get_user_context] = lambda: UserContext(
        user_id="reviewer", tenant_id="tenant-a"
    )
    app.dependency_overrides[get_document_draft_service] = lambda: service
    app.dependency_overrides[get_paper_db] = lambda: db
    body = {
        "role": "rent_invoice",
        "document": {"source_document_id": "source", "fields": {}},
        "reviewed": True,
        "reason": "Checked",
    }
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        saved = await client.post("/v1/paper/document-drafts", json=body)
        forged = await client.post(
            "/v1/paper/document-drafts", json={**body, "tenant_id": "other", "reviewed_by": "admin"}
        )
        listed = await client.get(
            "/v1/paper/document-drafts",
            params={"role": "rent_invoice", "status": "reviewed", "limit": 1, "tenant_id": "other"},
        )
        invalid = await client.get("/v1/paper/document-drafts", params={"limit": 101})
        missing = await client.get("/v1/paper/document-drafts/missing/versions/1")
    assert saved.status_code == 201 and saved.json()["reviewed_by"] == "reviewer"
    assert forged.status_code == invalid.status_code == 422
    assert listed.status_code == 200 and listed.json()["total"] == 1
    assert missing.status_code == 404
    assert service.create.await_args.kwargs["actor"].tenant_id == "tenant-a"
    assert service.list_latest.await_args.kwargs["query"].role == "rent_invoice"
    db.commit.assert_awaited_once()
