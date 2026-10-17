"""PAPER APIs publish only explicitly authorized and committed decisions."""

from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import FastAPI

from src.api.auth import UserContext, get_user_context
from src.api.paper_routes import (
    get_agreement_actor,
    get_agreement_service,
    get_paper_db,
    get_paper_settings,
    router,
)
from src.paper.contracts import AgreementActor, AgreementDraft, AgreementIdentity, AgreementVersion
from src.paper.errors import AgreementMasterError
from src.paper.schemas import RentAgreementSchema
from src.paper.service import AgreementMasterService
from src.paper.settings import AgreementMasterSettings


def _version() -> AgreementVersion:
    return AgreementVersion(
        agreement_id="agreement-1",
        tenant_id="tenant-1",
        version_number=1,
        identity=AgreementIdentity(
            vendor_id="vendor-1", store_id="store-1", contract_number="RA-1"
        ),
        draft=AgreementDraft(
            terms=RentAgreementSchema(vendor_name="Landlord"),
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 12, 31),
            source_document_ids=("source-1",),
            change_reason="Initial terms",
        ),
        created_by="author",
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def setup() -> tuple[FastAPI, AsyncMock, AsyncMock]:
    app = FastAPI()
    app.include_router(router)
    service = AsyncMock(spec=AgreementMasterService)
    service.create_draft.return_value = _version()
    service.revise.return_value = _version()
    service.approve.return_value = _version()
    service.get_version.return_value = _version()
    service.list_versions.return_value = (_version(),)
    service.find_approved.return_value = None
    db = AsyncMock()
    app.dependency_overrides[get_user_context] = lambda: UserContext(
        user_id="reviewer", tenant_id="tenant-1"
    )
    app.dependency_overrides[get_agreement_actor] = lambda: AgreementActor(
        tenant_id="tenant-1", user_id="reviewer", can_approve=True
    )
    app.dependency_overrides[get_agreement_service] = lambda: service
    app.dependency_overrides[get_paper_db] = lambda: db
    app.dependency_overrides[get_paper_settings] = lambda: AgreementMasterSettings()
    return app, service, db


@pytest.mark.asyncio
async def test_create_commits_and_does_not_accept_tenant_override(
    setup: tuple[FastAPI, AsyncMock, AsyncMock],
) -> None:
    app, service, db = setup
    payload = {
        "identity": _version().identity.model_dump(),
        "draft": _version().draft.model_dump(mode="json"),
    }
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/v1/paper/agreements", json=payload)
        invalid = await client.post("/v1/paper/agreements", json={**payload, "tenant_id": "other"})
    assert response.status_code == 201
    assert response.json()["status"] == "draft"
    assert invalid.status_code == 422
    db.commit.assert_awaited_once()
    assert service.create_draft.await_args.kwargs["actor"].tenant_id == "tenant-1"


@pytest.mark.asyncio
async def test_revision_has_optimistic_expected_version(
    setup: tuple[FastAPI, AsyncMock, AsyncMock],
) -> None:
    app, service, db = setup
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        result = await client.post(
            "/v1/paper/agreements/agreement-1/versions",
            json={"expected_version": 1, "draft": _version().draft.model_dump(mode="json")},
        )
    assert result.status_code == 201
    assert service.revise.await_args.kwargs["expected_version"] == 1
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_approval_cannot_supply_approver_or_authority(
    setup: tuple[FastAPI, AsyncMock, AsyncMock],
) -> None:
    app, service, db = setup
    payload = {
        "classification": "psak73",
        "rule_set_id": "accounting-policy",
        "rule_set_version": "1",
        "reason": "Reviewed",
    }
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        good = await client.post(
            "/v1/paper/agreements/agreement-1/versions/1/approval", json=payload
        )
        bad = await client.post(
            "/v1/paper/agreements/agreement-1/versions/1/approval",
            json={**payload, "approved_by": "someone-else", "can_approve": True},
        )
    assert good.status_code == 200
    assert bad.status_code == 422
    assert service.approve.await_args.kwargs["actor"].user_id == "reviewer"
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "code,status",
    [
        ("forbidden", 403),
        ("not_found", 404),
        ("conflict", 409),
        ("invalid_approval", 422),
        ("timeout", 504),
    ],
)
async def test_failed_approval_is_not_committed(
    setup: tuple[FastAPI, AsyncMock, AsyncMock], code: str, status: int
) -> None:
    app, service, db = setup
    service.approve.side_effect = AgreementMasterError(code, "Safe business failure")
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/v1/paper/agreements/agreement-1/versions/1/approval",
            json={
                "classification": "psak73",
                "rule_set_id": "rule",
                "rule_set_version": "1",
                "reason": "Review",
            },
        )
    assert response.status_code == status
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_approved_lookup_is_scoped_and_returns_404_for_no_match(
    setup: tuple[FastAPI, AsyncMock, AsyncMock],
) -> None:
    app, service, db = setup
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/v1/paper/agreements/approved",
            params={
                "vendor_id": "vendor-1",
                "store_id": "store-1",
                "contract_number": "RA-1",
                "as_of": "2026-06-01",
            },
        )
    assert response.status_code == 404
    assert service.find_approved.await_args.kwargs["lookup"].as_of == date(2026, 6, 1)
    assert service.find_approved.await_args.kwargs["actor"].tenant_id == "tenant-1"
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_schema_discovery_returns_portable_external_contract(
    setup: tuple[FastAPI, AsyncMock, AsyncMock],
) -> None:
    app, _, db = setup
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/v1/paper/schemas/rent_agreement")
        missing = await client.get("/v1/paper/schemas/fabricated")
        unsupported = await client.get("/v1/paper/schemas/rent_agreement", params={"version": "99"})
    assert response.status_code == 200
    assert response.json()["schema_id"] == "paper.rent_agreement"
    assert response.json()["json_schema"]["type"] == "object"
    assert missing.status_code == unsupported.status_code == 404
    db.execute.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "stored_role,stored_tenant,allowed",
    [("accountant", "tenant-1", True), ("member", "tenant-1", False), ("admin", "other", False)],
)
async def test_approval_authority_comes_from_persisted_tenant_user(
    stored_role: str, stored_tenant: str, allowed: bool
) -> None:
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = SimpleNamespace(
        role=stored_role, tenant_id=stored_tenant
    )
    db.execute.return_value = result
    actor = await get_agreement_actor(
        user=UserContext(user_id="reviewer", tenant_id="tenant-1"),
        db=db,
        settings=AgreementMasterSettings(),
    )
    assert actor.can_approve is allowed
    statement = str(db.execute.await_args.args[0])
    assert "users.tenant_id" in statement and "users.id" in statement
