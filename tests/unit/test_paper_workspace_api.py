"""Workspace transport enforces authenticated scope and bounded read-only queries."""

from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI

from src.api.auth import UserContext, get_user_context
from src.api.paper_workspace_routes import get_workspace_index, router
from src.paper.workspace.contracts import WorkspacePage
from src.services.paper_workspace_index import PaperWorkspaceIndexService


@pytest.mark.asyncio
async def test_workspace_filters_and_scope_are_server_validated() -> None:
    app = FastAPI()
    app.include_router(router)
    service = AsyncMock(spec=PaperWorkspaceIndexService)
    service.cases.return_value = WorkspacePage(items=(), total=0, limit=5, offset=10)
    service.contracts.return_value = WorkspacePage(items=(), total=0, limit=20, offset=0)
    service.documents.return_value = WorkspacePage(items=(), total=0, limit=1, offset=0)
    app.dependency_overrides[get_user_context] = lambda: UserContext(
        user_id="reviewer", tenant_id="tenant-a"
    )
    app.dependency_overrides[get_workspace_index] = lambda: service
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/v1/paper/workspace/cases",
            params={
                "q": "invoice",
                "status": "incomplete",
                "agreement_id": "contract-a",
                "association_kind": "confirmed",
                "limit": 5,
                "offset": 10,
                "tenant_id": "other",
            },
        )
        invalid = await client.get("/v1/paper/workspace/cases", params={"limit": 101})
        invalid_status = await client.get(
            "/v1/paper/workspace/contracts", params={"status": "wrong"}
        )
        document = await client.get(
            "/v1/paper/workspace/documents",
            params={"job_id": "job-a", "workflow_status": "agreement_draft", "limit": 1},
        )
    assert response.status_code == 200
    assert invalid.status_code == invalid_status.status_code == 422
    args = service.cases.await_args.args
    assert args[0] == "tenant-a"
    assert args[1].q == "invoice" and args[1].offset == 10
    assert document.status_code == 200
    assert service.documents.await_args.args[1].job_id == "job-a"
