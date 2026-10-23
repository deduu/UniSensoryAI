"""PAPER case endpoints trust host roles and commit durable outcomes."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import FastAPI

from src.api.auth import UserContext
from src.api.paper_case_routes import get_invoice_actor, get_invoice_case_service, router
from src.api.paper_routes import get_paper_db
from src.paper.contracts import AgreementActor
from src.paper.errors import AgreementMasterError
from src.paper.reconciliation.contracts import InvoiceCaseVersion
from src.paper.reconciliation.engine import ReconciliationEngine
from src.paper.reconciliation.settings import ReconciliationSettings
from src.paper.reconciliation.workflow import InvoiceCaseService
from tests.unit.test_paper_case_workflow import package, reference

_Setup = tuple[FastAPI, AsyncMock, AsyncMock]


@pytest.fixture
def setup() -> _Setup:
    app = FastAPI()
    app.include_router(router)
    assessment = ReconciliationEngine(ReconciliationSettings()).assess(
        package(), agreement_start=reference(), agreement_end=reference(), tenant_id="tenant-1"
    )
    case = InvoiceCaseVersion(
        case_id="case-1",
        tenant_id="tenant-1",
        version_number=1,
        package=package(),
        assessment=assessment,
        created_by="author",
        created_at=datetime.now(timezone.utc),
    )
    service = AsyncMock(spec=InvoiceCaseService)
    service.create_case.return_value = case
    service.revise_case.return_value = case
    service.decide_case.return_value = case
    service.get_version.return_value = case
    service.list_versions.return_value = (case,)
    service.list_cases.return_value = (case,)
    db = AsyncMock()
    app.dependency_overrides[get_invoice_actor] = lambda: AgreementActor(
        user_id="reviewer",
        tenant_id="tenant-1",
        can_approve=True,
    )
    app.dependency_overrides[get_invoice_case_service] = lambda: service
    app.dependency_overrides[get_paper_db] = lambda: db
    return app, service, db


@pytest.mark.asyncio
async def test_case_creation_commits_and_rejects_caller_authority(setup: _Setup) -> None:
    app, service, db = setup
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/v1/paper/cases", json=package().model_dump(mode="json"))
        invalid = await client.post(
            "/v1/paper/cases",
            json={
                **package().model_dump(mode="json"),
                "tenant_id": "other",
                "can_approve": True,
            },
        )
    assert response.status_code == 201
    assert response.json()["status"] == "matched"
    assert invalid.status_code == 422
    assert service.create_case.await_args.kwargs["actor"].tenant_id == "tenant-1"
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_case_revision_passes_expected_version(setup: _Setup) -> None:
    app, service, db = setup
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/v1/paper/cases/case-1/versions",
            json={
                "expected_version": 1,
                "package": package().model_dump(mode="json"),
            },
        )
    assert response.status_code == 201
    assert service.revise_case.await_args.kwargs["expected_version"] == 1
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_manual_case_routes_cannot_claim_saved_document_review_provenance(
    setup: _Setup,
) -> None:
    app, service, _ = setup
    payload = package().model_dump(mode="json")
    payload["document_draft_references"] = [
        {
            "draft_id": "unverified-draft",
            "version_number": 9,
            "role": "rent_invoice",
            "source_document_id": "invoice-source",
            "reviewed_by": "someone-else",
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
        }
    ]
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        initial = await client.post("/v1/paper/cases", json=payload)
        revision = await client.post(
            "/v1/paper/cases/case-1/versions", json={"expected_version": 1, "package": payload}
        )
    assert initial.status_code == revision.status_code == 201
    assert service.create_case.await_args.kwargs["package"].document_draft_references == ()
    assert service.revise_case.await_args.kwargs["package"].document_draft_references == ()


@pytest.mark.asyncio
async def test_ap_decision_cannot_supply_reviewer_or_reference(setup: _Setup) -> None:
    app, service, db = setup
    payload = {"action": "approve", "reason": "Reviewed package"}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/v1/paper/cases/case-1/versions/1/decision", json=payload)
        invalid = await client.post(
            "/v1/paper/cases/case-1/versions/1/decision",
            json={
                **payload,
                "decided_by": "other",
                "agreement_reference": {"version_number": 99},
            },
        )
    assert response.status_code == 200
    assert invalid.status_code == 422
    assert service.decide_case.await_args.kwargs["expected_version"] == 1
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "code,status",
    [("conflict", 409), ("forbidden", 403), ("invalid_approval", 422), ("timeout", 504)],
)
async def test_failed_ap_decision_never_commits(setup: _Setup, code: str, status: int) -> None:
    app, service, db = setup
    service.decide_case.side_effect = AgreementMasterError(code, "Safe case error")
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/v1/paper/cases/case-1/versions/1/decision",
            json={"action": "approve", "reason": "Reviewed"},
        )
    assert response.status_code == status
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_case_lists_and_history_are_paginated(setup: _Setup) -> None:
    app, service, db = setup
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        listing = await client.get("/v1/paper/cases?limit=10&offset=2")
        history = await client.get("/v1/paper/cases/case-1/versions?limit=5&offset=1")
        exact = await client.get("/v1/paper/cases/case-1/versions/1")
        invalid = await client.get("/v1/paper/cases?limit=101")
    assert listing.status_code == history.status_code == exact.status_code == 200
    assert invalid.status_code == 422
    assert service.list_cases.await_args.kwargs["limit"] == 10
    assert service.list_versions.await_args.kwargs["offset"] == 1
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_case_actor_uses_scoped_persisted_role() -> None:
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = SimpleNamespace(tenant_id="tenant-1", role="finance")
    db.execute.return_value = result
    actor = await get_invoice_actor(
        user=UserContext(user_id="reviewer", tenant_id="tenant-1"),
        db=db,
        settings=ReconciliationSettings(approver_roles=("finance",)),
    )
    assert actor.can_approve is True
    query = db.execute.await_args.args[0]
    assert query.compile().params == {"id_1": "reviewer", "tenant_id_1": "tenant-1"}
    result.scalar_one_or_none.return_value = SimpleNamespace(tenant_id="other", role="finance")
    forbidden = await get_invoice_actor(
        user=UserContext(user_id="reviewer", tenant_id="tenant-1"),
        db=db,
        settings=ReconciliationSettings(approver_roles=("finance",)),
    )
    assert forbidden.can_approve is False


@pytest.mark.asyncio
async def test_injected_invalid_policy_is_sanitized() -> None:
    from fastapi import HTTPException
    from starlette.requests import Request

    from src.api.paper_case_routes import get_base_reconciliation_settings

    app = FastAPI()
    app.state.paper_reconciliation_settings = {"override_codes": ["private-invalid-value"]}
    with pytest.raises(HTTPException) as error:
        await get_base_reconciliation_settings(Request({"type": "http", "app": app}))
    assert error.value.status_code == 503
    assert "private-invalid-value" not in str(error.value.detail)
