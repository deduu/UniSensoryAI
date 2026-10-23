"""PAPER UI reads are scoped and expose trusted review policy only."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import FastAPI
from pydantic import ValidationError

from src.api.auth import UserContext, get_user_context
from src.api.paper_case_routes import (
    get_base_reconciliation_settings,
    get_invoice_actor,
    get_reconciliation_settings,
    review_router,
)
from src.api.paper_routes import (
    get_agreement_actor,
    get_agreement_service,
    get_paper_db,
    get_paper_settings,
    router,
)
from src.paper.contracts import AgreementActor
from src.paper.errors import AgreementMasterError
from src.paper.ports import BaseAgreementRepository
from src.paper.reconciliation.settings import ReconciliationSettings
from src.paper.service import AgreementMasterService
from src.paper.settings import AgreementMasterSettings
from tests.unit.test_paper_api import _version


@pytest.mark.asyncio
async def test_agreement_listing_passes_validated_actor_tenant_and_page() -> None:
    repository = AsyncMock(spec=BaseAgreementRepository)
    snapshot = _version()
    repository.list_latest = AsyncMock(return_value=(snapshot,))
    actor = AgreementActor(user_id="member", tenant_id="tenant-1")
    result = await AgreementMasterService(repository).list_agreements(
        actor=actor, limit=10, offset=2
    )
    assert result == (snapshot,)
    repository.list_latest.assert_awaited_once_with(tenant_id="tenant-1", limit=10, offset=2)
    repository.get_version.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("limit,offset", [(0, 0), (101, 0), (10, -1)])
async def test_agreement_listing_rejects_invalid_page_before_storage(
    limit: int, offset: int
) -> None:
    repository = AsyncMock(spec=BaseAgreementRepository)
    repository.list_latest = AsyncMock()
    with pytest.raises(ValidationError):
        await AgreementMasterService(repository).list_agreements(
            actor=AgreementActor(user_id="member", tenant_id="tenant-1"),
            limit=limit,
            offset=offset,
        )
    repository.list_latest.assert_not_awaited()


@pytest.mark.asyncio
async def test_agreement_listing_preserves_storage_deadline() -> None:
    repository = AsyncMock(spec=BaseAgreementRepository)
    repository.list_latest = AsyncMock(side_effect=TimeoutError)
    with pytest.raises(AgreementMasterError) as error:
        await AgreementMasterService(repository).list_agreements(
            actor=AgreementActor(user_id="member", tenant_id="tenant-1")
        )
    assert error.value.code == "timeout"


@pytest.mark.asyncio
async def test_agreement_listing_route_is_read_only_and_validates_pagination() -> None:
    app = FastAPI()
    app.include_router(router)
    service = AsyncMock()
    snapshot = _version()
    service.list_agreements.return_value = (snapshot,)
    actor = AgreementActor(user_id="member", tenant_id="tenant-1")
    db = AsyncMock()
    app.dependency_overrides[get_user_context] = lambda: UserContext(
        user_id="member", tenant_id="tenant-1"
    )
    app.dependency_overrides[get_agreement_actor] = lambda: actor
    app.dependency_overrides[get_agreement_service] = lambda: service
    app.dependency_overrides[get_paper_db] = lambda: db
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/v1/paper/agreements", params={"limit": 10, "offset": 2})
        invalid = await client.get("/v1/paper/agreements", params={"limit": 101})
    assert response.status_code == 200
    assert response.json() == [snapshot.model_dump(mode="json")]
    assert invalid.status_code == 422
    service.list_agreements.assert_awaited_once_with(actor=actor, limit=10, offset=2)
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_review_context_uses_both_host_policies_and_actor_permissions() -> None:
    app = FastAPI()
    app.include_router(review_router)
    agreement_settings = AgreementMasterSettings(
        required_agreement_fields=("vendor_name", "currency"),
        required_fields_by_rent_type={"fixed": ("fixed_rent",)},
        require_independent_approval=True,
    )
    case_settings = ReconciliationSettings(
        policy_id="external.invoice_policy",
        policy_version="2026.2",
        required_invoice_fields=("invoice_number",),
        required_tax_fields=("tax_invoice_number",),
        required_documents=("rent_invoice", "supporting_document"),
        required_supporting_types=("handover",),
        override_codes=("bank_mismatch",),
    )
    db = AsyncMock()
    app.dependency_overrides[get_user_context] = lambda: UserContext(
        user_id="reviewer", tenant_id="tenant-1"
    )
    app.dependency_overrides[get_agreement_actor] = lambda: AgreementActor(
        user_id="reviewer", tenant_id="tenant-1", can_approve=False
    )
    app.dependency_overrides[get_invoice_actor] = lambda: AgreementActor(
        user_id="reviewer", tenant_id="tenant-1", can_approve=True
    )
    app.dependency_overrides[get_paper_settings] = lambda: agreement_settings
    app.dependency_overrides[get_reconciliation_settings] = lambda: case_settings
    app.dependency_overrides[get_base_reconciliation_settings] = lambda: case_settings
    app.dependency_overrides[get_paper_db] = lambda: db
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/v1/paper/review-context")
    assert response.status_code == 200
    assert response.json() == {
        "user_id": "reviewer",
        "can_approve_agreements": False,
        "can_decide_cases": True,
        "agreement_required_fields": ["vendor_name", "currency"],
        "agreement_required_fields_by_rent_type": {"fixed": ["fixed_rent"]},
        "required_invoice_fields": ["invoice_number"],
        "required_tax_fields": ["tax_invoice_number"],
        "required_documents": ["rent_invoice", "supporting_document"],
        "required_supporting_types": ["handover"],
        "override_codes": ["bank_mismatch"],
        "policy_id": "external.invoice_policy",
        "policy_version": "2026.2",
        "field_requirements": [],
        "enabled_rules": [],
        "allow_withholding_without_vat_invoice": False,
        "withholding_required_supporting_types": ["withholding_certificate"],
        "require_independent_agreement_approval": True,
        "require_independent_case_approval": False,
    }
    db.commit.assert_not_awaited()
    db.execute.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("stored_tenant", ["tenant-1", "another-tenant", None])
async def test_review_context_resolves_persisted_tenant_roles(stored_tenant: str | None) -> None:
    app = FastAPI()
    app.include_router(review_router)
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = (
        SimpleNamespace(role="accountant", tenant_id=stored_tenant)
        if stored_tenant is not None
        else None
    )
    db.execute.return_value = result
    app.dependency_overrides[get_user_context] = lambda: UserContext(
        user_id="reviewer", tenant_id="tenant-1"
    )
    app.dependency_overrides[get_paper_db] = lambda: db
    app.dependency_overrides[get_paper_settings] = lambda: AgreementMasterSettings(
        approver_roles=("agreement-reviewer",)
    )
    app.dependency_overrides[get_base_reconciliation_settings] = lambda: ReconciliationSettings(
        approver_roles=("accountant",)
    )
    app.dependency_overrides[get_reconciliation_settings] = lambda: ReconciliationSettings(
        approver_roles=("accountant",)
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/v1/paper/review-context")
    assert response.status_code == 200
    assert response.json()["can_approve_agreements"] is False
    assert response.json()["can_decide_cases"] is (stored_tenant == "tenant-1")
    assert db.execute.await_count == 2
    for call in db.execute.await_args_list:
        statement = str(call.args[0])
        assert "users.id" in statement and "users.tenant_id" in statement
    db.commit.assert_not_awaited()
