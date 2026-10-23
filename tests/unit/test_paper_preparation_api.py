"""Preparation transport shares authenticated scope and never trusts source payloads."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI

from src.api.paper_case_routes import get_invoice_actor
from src.api.paper_preparation_routes import get_case_preparation_service, router
from src.api.paper_routes import get_paper_db
from src.paper.contracts import AgreementActor
from src.paper.preparation.service import CasePreparationService
from src.paper.reconciliation.contracts import InvoiceCaseVersion
from src.paper.reconciliation.engine import ReconciliationEngine
from src.paper.reconciliation.settings import ReconciliationSettings
from tests.unit.test_paper_case_preparation import draft, request


@pytest.mark.asyncio
async def test_preparation_rejects_raw_documents_and_exposes_no_client_tenant() -> None:
    app = FastAPI()
    app.include_router(router)
    service = AsyncMock()
    app.dependency_overrides[get_invoice_actor] = lambda: AgreementActor(
        tenant_id="tenant-a", user_id="reviewer"
    )
    app.dependency_overrides[get_case_preparation_service] = lambda: service
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        payload = {
            "identity": {"vendor_id": "v", "store_id": "s", "contract_number": "c"},
            "invoice": {"source_document_id": "unreviewed", "fields": {}},
        }
        raw = await client.post("/v1/paper/cases/preparation/readiness", json=payload)
        spoofed = await client.post(
            "/v1/paper/cases/preparation/readiness", json={**payload, "tenant_id": "other"}
        )
    assert raw.status_code == spoofed.status_code == 422
    service.check.assert_not_awaited()


@pytest.mark.asyncio
async def test_authority_change_after_preview_never_commits_a_case() -> None:
    app = FastAPI()
    app.include_router(router)
    drafts, cases, db = AsyncMock(), AsyncMock(), AsyncMock()
    drafts.get_version.return_value = draft()
    settings = ReconciliationSettings()
    service = CasePreparationService(drafts, cases, settings)
    actor = AgreementActor(tenant_id="tenant-1", user_id="reviewer")
    resolved = await service.resolve(actor=actor, request=request())
    service.check = AsyncMock(return_value=SimpleNamespace(ready=True))
    assessment = ReconciliationEngine(settings).assess(
        resolved,
        agreement_start=None,
        agreement_end=None,
        tenant_id=actor.tenant_id,
    )
    cases.create_case.return_value = InvoiceCaseVersion(
        case_id="case-race",
        tenant_id=actor.tenant_id,
        version_number=1,
        package=resolved,
        assessment=assessment,
        created_by=actor.user_id,
        created_at=datetime.now(timezone.utc),
    )
    app.dependency_overrides[get_invoice_actor] = lambda: actor
    app.dependency_overrides[get_case_preparation_service] = lambda: service
    app.dependency_overrides[get_paper_db] = lambda: db
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/v1/paper/cases/from-drafts", json=request().model_dump(mode="json")
        )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "conflict"
    cases.create_case.assert_awaited_once()
    db.commit.assert_not_awaited()
