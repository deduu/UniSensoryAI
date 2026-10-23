"""Candidate discovery is tenant scoped and read-only despite its POST search body."""

from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI

from src.api.paper_case_routes import (
    get_contract_association_service,
    get_invoice_actor,
    router,
)
from src.api.paper_routes import get_paper_db
from src.paper.association.candidates import AssociationCandidates
from src.paper.association.service import AssociationService
from src.paper.contracts import AgreementActor
from tests.unit.test_paper_case_workflow import package


@pytest.mark.asyncio
async def test_candidates_use_trusted_tenant_and_never_commit() -> None:
    app = FastAPI()
    app.include_router(router)
    service = AsyncMock(spec=AssociationService)
    service.suggest.return_value = AssociationCandidates(
        candidates=(),
        state="no_match",
        offset=0,
        limit=25,
        next_offset=None,
        has_more=False,
        exhaustive=True,
        policy_id="paper.contract_association",
        policy_version="1",
    )
    db = AsyncMock()
    app.dependency_overrides[get_invoice_actor] = lambda: AgreementActor(
        tenant_id="trusted",
        user_id="reviewer",
        can_approve=False,
    )
    app.dependency_overrides[get_contract_association_service] = lambda: service
    app.dependency_overrides[get_paper_db] = lambda: db
    payload = {"invoice": package().invoice.model_dump(mode="json")}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        result = await client.post("/v1/paper/cases/association/candidates", json=payload)
        forged = await client.post(
            "/v1/paper/cases/association/candidates",
            json={**payload, "tenant_id": "foreign"},
        )
    assert result.status_code == 200
    assert result.json()["state"] == "no_match"
    assert service.suggest.await_args.kwargs["actor"].tenant_id == "trusted"
    assert forged.status_code == 422
    db.commit.assert_not_awaited()
