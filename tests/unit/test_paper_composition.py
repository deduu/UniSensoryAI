"""Deployment policy is validated, isolated, and loaded asynchronously."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from starlette.requests import Request

from src.api.paper_routes import get_paper_settings
from src.paper.composition import load_agreement_settings
from src.paper.errors import AgreementMasterError
from src.paper.settings import AgreementMasterSettings


@pytest.mark.asyncio
async def test_packaged_policy_matches_embedding_defaults() -> None:
    settings = await load_agreement_settings()
    assert settings == AgreementMasterSettings()
    assert settings.required_fields_by_rent_type["fixed"] == ("fixed_rent",)


@pytest.mark.asyncio
async def test_host_policy_can_require_independent_review(tmp_path: Path) -> None:
    path = tmp_path / "paper.yaml"
    path.write_text(
        "require_independent_approval: true\napprover_roles: [finance]\n", encoding="utf-8"
    )
    settings = await load_agreement_settings(path)
    assert settings.require_independent_approval is True
    assert settings.approver_roles == ("finance",)


@pytest.mark.asyncio
async def test_invalid_policy_errors_do_not_disclose_path_or_values(tmp_path: Path) -> None:
    path = tmp_path / "private-policy.yaml"
    path.write_text("approver_roles: []\n", encoding="utf-8")
    with pytest.raises(AgreementMasterError) as error:
        await load_agreement_settings(path)
    assert error.value.code == "invalid_configuration"
    assert str(path) not in str(error.value)


@pytest.mark.asyncio
async def test_policy_cache_is_owned_by_app_and_serializes_first_load() -> None:
    app = FastAPI()
    request = Request({"type": "http", "app": app})
    settings = AgreementMasterSettings()
    with patch(
        "src.api.paper_routes.load_agreement_settings", new=AsyncMock(return_value=settings)
    ) as loader:
        first, second = await asyncio.gather(
            get_paper_settings(request), get_paper_settings(request)
        )
    assert first == second == settings
    loader.assert_awaited_once()
    assert not hasattr(FastAPI().state, "paper_settings")
