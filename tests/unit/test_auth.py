"""Tests for src/api/auth.py — JWT authentication."""

import os
import sys
import time
from datetime import timedelta
from unittest.mock import MagicMock

import pytest

# Mock heavy ML modules
_MOCK_MODULES = [
    "torch", "torch.cuda", "torch.nn", "torch.nn.functional",
    "torchvision", "torchvision.transforms",
    "transformers", "accelerate", "bitsandbytes",
    "nvitop",
    "fitz", "pymupdf", "pymupdf.extra", "pymupdf._extra",
]
for mod in _MOCK_MODULES:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

from fastapi import HTTPException

os.environ["JWT_SECRET_KEY"] = "test-secret-key-32bytes-minimum!"
os.environ["AUTH_ENABLED"] = "true"

from src.api.auth import (
    AuthConfig,
    create_access_token,
    get_current_user,
    verify_token,
)


class TestAuthConfig:
    def test_is_enabled_default(self):
        """Auth should be enabled by default."""
        os.environ["AUTH_ENABLED"] = "true"
        assert AuthConfig.is_enabled() is True

    def test_is_disabled(self):
        """Auth should be disabled when AUTH_ENABLED=false."""
        os.environ["AUTH_ENABLED"] = "false"
        result = AuthConfig.is_enabled()
        os.environ["AUTH_ENABLED"] = "true"  # restore
        assert result is False

    def test_get_secret_key(self):
        """Should return the JWT_SECRET_KEY env var."""
        assert AuthConfig.get_secret_key() == "test-secret-key-32bytes-minimum!"

    def test_get_algorithm(self):
        """Default algorithm should be HS256."""
        assert AuthConfig.get_algorithm() == "HS256"


class TestCreateAccessToken:
    def test_creates_valid_token(self):
        """Token should be decodable."""
        token = create_access_token({"sub": "user123", "role": "admin"})
        assert isinstance(token, str)
        assert len(token) > 0

    def test_token_contains_payload(self):
        """Decoded token should contain original payload."""
        token = create_access_token({"sub": "user123", "role": "admin"})
        payload = verify_token(token)
        assert payload["sub"] == "user123"
        assert payload["role"] == "admin"

    def test_custom_expiration(self):
        """Custom expiration should be respected."""
        token = create_access_token(
            {"sub": "user123"},
            expires_delta=timedelta(hours=2),
        )
        payload = verify_token(token)
        assert payload["sub"] == "user123"


class TestVerifyToken:
    def test_valid_token(self):
        """Valid token should return payload."""
        token = create_access_token({"sub": "test"})
        payload = verify_token(token)
        assert payload["sub"] == "test"
        assert "exp" in payload
        assert "iat" in payload

    def test_expired_token(self):
        """Expired token should raise 401."""
        token = create_access_token(
            {"sub": "test"},
            expires_delta=timedelta(seconds=-1),
        )
        with pytest.raises(HTTPException) as exc_info:
            verify_token(token)
        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail.lower()

    def test_invalid_token(self):
        """Garbled token should raise 401."""
        with pytest.raises(HTTPException) as exc_info:
            verify_token("not.a.valid.token")
        assert exc_info.value.status_code == 401

    def test_tampered_token(self):
        """Token signed with different key should fail."""
        import jwt

        token = jwt.encode(
            {"sub": "hacker"},
            "wrong-secret",
            algorithm="HS256",
        )
        with pytest.raises(HTTPException) as exc_info:
            verify_token(token)
        assert exc_info.value.status_code == 401


class TestGetCurrentUser:
    @pytest.mark.asyncio
    async def test_auth_disabled_returns_none(self):
        """When auth is disabled, should return None."""
        os.environ["AUTH_ENABLED"] = "false"
        try:
            result = await get_current_user(credentials=None)
            assert result is None
        finally:
            os.environ["AUTH_ENABLED"] = "true"

    @pytest.mark.asyncio
    async def test_missing_credentials_raises(self):
        """Missing credentials should raise 401."""
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials=None)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_valid_credentials_returns_payload(self):
        """Valid Bearer token should return decoded payload."""
        from fastapi.security import HTTPAuthorizationCredentials

        token = create_access_token({"sub": "user1", "role": "admin"})
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        result = await get_current_user(credentials=creds)
        assert result["sub"] == "user1"
