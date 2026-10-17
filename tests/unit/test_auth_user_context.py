"""Tests for UserContext and the get_user_context dependency."""

import os
import sys
from unittest.mock import MagicMock

import pytest

# Mock heavy ML modules (mirrors test_auth.py)
_MOCK_MODULES = [
    "torch", "torch.cuda", "torch.nn", "torch.nn.functional",
    "torchvision", "torchvision.transforms",
    "transformers", "accelerate", "bitsandbytes",
    "nvitop",
]
for mod in _MOCK_MODULES:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

os.environ["JWT_SECRET_KEY"] = "test-secret-key-32bytes-minimum!"

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from src.api.auth import (
    UserContext,
    create_access_token,
    get_user_context,
    resolve_tenant_id,
    DEFAULT_TENANT_ID,
)


class TestUserContext:
    def test_construct_minimal(self):
        ctx = UserContext(user_id="u-1", tenant_id="t-1")
        assert ctx.user_id == "u-1"
        assert ctx.tenant_id == "t-1"
        assert ctx.email is None

    def test_construct_with_email(self):
        ctx = UserContext(user_id="u-1", tenant_id="t-1", email="a@x.com")
        assert ctx.email == "a@x.com"

    def test_tenant_id_required(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            UserContext(user_id="u-1")  # type: ignore[call-arg]


class TestGetUserContextAuthDisabled:
    @pytest.mark.asyncio
    async def test_returns_synthetic_context_when_disabled(self, monkeypatch):
        """When AUTH_ENABLED=false, return synthetic context with DEFAULT_TENANT_ID."""
        monkeypatch.setenv("AUTH_ENABLED", "false")
        ctx = await get_user_context(credentials=None)
        assert ctx.tenant_id == DEFAULT_TENANT_ID
        assert ctx.user_id  # not empty


class TestGetUserContextAuthEnabled:
    @pytest.mark.asyncio
    async def test_missing_credentials_raises_401(self, monkeypatch):
        monkeypatch.setenv("AUTH_ENABLED", "true")
        with pytest.raises(HTTPException) as exc:
            await get_user_context(credentials=None)
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_valid_token_returns_context(self, monkeypatch):
        monkeypatch.setenv("AUTH_ENABLED", "true")
        token = create_access_token({
            "sub": "u-42",
            "tenant_id": "t-acme",
            "email": "alice@acme.com",
        })
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        ctx = await get_user_context(credentials=creds)
        assert ctx.user_id == "u-42"
        assert ctx.tenant_id == "t-acme"
        assert ctx.email == "alice@acme.com"

    @pytest.mark.asyncio
    async def test_token_without_tenant_id_raises_401(self, monkeypatch):
        monkeypatch.setenv("AUTH_ENABLED", "true")
        token = create_access_token({"sub": "u-1"})  # no tenant_id claim
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        with pytest.raises(HTTPException) as exc:
            await get_user_context(credentials=creds)
        assert exc.value.status_code == 401


class TestResolveTenantId:
    """resolve_tenant_id remains for backward compat with dict-style user payloads."""

    def test_none_returns_default(self):
        assert resolve_tenant_id(None) == DEFAULT_TENANT_ID

    def test_dict_with_tenant_id(self):
        assert resolve_tenant_id({"sub": "u-1", "tenant_id": "t-x"}) == "t-x"

    def test_user_context_input(self):
        """resolve_tenant_id should also accept a UserContext."""
        ctx = UserContext(user_id="u-1", tenant_id="t-y")
        assert resolve_tenant_id(ctx) == "t-y"

    def test_dict_missing_tenant_id_raises(self):
        with pytest.raises(HTTPException) as exc:
            resolve_tenant_id({"sub": "u-1"})
        assert exc.value.status_code == 401
