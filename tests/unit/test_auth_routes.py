"""Tests for src/api/auth_routes.py — OAuth login/callback/me/logout.

The OAuth provider exchange (``authorize_access_token`` and any HTTP calls
to Google/GitHub) is mocked. We exercise the route plumbing: provider
gating, user upsert, JWT cookie issuance, and ``/me`` round-tripping.
"""

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

# Mock heavy ML modules so importing src.api.server doesn't drag torch in.
_MOCK_MODULES = [
    "torch", "torch.cuda", "torch.nn", "torch.nn.functional",
    "torchvision", "torchvision.transforms",
    "transformers", "accelerate", "bitsandbytes",
    "nvitop", "fitz", "pymupdf", "pymupdf.extra", "pymupdf._extra",
]
for mod in _MOCK_MODULES:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-32bytes-minimum!")
os.environ["OAUTH_GOOGLE_CLIENT_ID"] = "test-google-id"
os.environ["OAUTH_GOOGLE_CLIENT_SECRET"] = "test-google-secret"
# Intentionally leave GitHub unconfigured to test the 503 path.
os.environ.pop("OAUTH_GITHUB_CLIENT_ID", None)
os.environ.pop("OAUTH_GITHUB_CLIENT_SECRET", None)

from contextlib import asynccontextmanager  # noqa: E402

from httpx import AsyncClient, ASGITransport  # noqa: E402

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from src.db.base import Base  # noqa: E402
from src.db.models import chat, document, ingestion, tenant, user as user_model  # noqa: E402,F401


@asynccontextmanager
async def _noop_lifespan(app):
    yield


@pytest_asyncio.fixture
async def db_session_factory():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    yield maker
    await engine.dispose()


@pytest_asyncio.fixture
async def app_with_db(db_session_factory):
    from src.api.server import app
    from src.db.session import get_db

    async def override_get_db():
        async with db_session_factory() as session:
            yield session

    app.router.lifespan_context = _noop_lifespan
    app.dependency_overrides[get_db] = override_get_db
    yield app
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_login_unknown_provider_returns_404(app_with_db):
    transport = ASGITransport(app=app_with_db)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/v1/auth/login/twitter")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_login_unconfigured_provider_returns_503(app_with_db):
    """GitHub has no client id/secret in this test env."""
    transport = ASGITransport(app=app_with_db)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/v1/auth/login/github")
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_login_google_redirects_to_provider(app_with_db):
    transport = ASGITransport(app=app_with_db)
    async with AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=False
    ) as client:
        resp = await client.get("/v1/auth/login/google")
    # Authlib redirects to Google's authorize endpoint
    assert resp.status_code in (302, 307)
    location = resp.headers.get("location", "")
    assert "accounts.google.com" in location or "oauth" in location.lower()


@pytest.mark.asyncio
async def test_callback_creates_user_sets_cookie_and_redirects(app_with_db):
    """Callback should upsert the user, set the access_token cookie, and
    redirect to FRONTEND_URL."""
    fake_token = {
        "access_token": "fake-google-access",
        "userinfo": {
            "sub": "google-sub-1",
            "email": "alice@acme.com",
            "name": "Alice",
        },
    }

    with patch(
        "src.api.auth_routes.oauth.create_client"
    ) as create_client:
        client_mock = MagicMock()
        client_mock.authorize_access_token = AsyncMock(return_value=fake_token)
        create_client.return_value = client_mock

        transport = ASGITransport(app=app_with_db)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
            follow_redirects=False,
        ) as client:
            resp = await client.get("/v1/auth/callback/google")

    assert resp.status_code == 302
    cookie_header = resp.headers.get("set-cookie", "")
    assert "access_token=" in cookie_header
    assert "HttpOnly" in cookie_header
    assert "SameSite=lax" in cookie_header.lower() or "samesite=lax" in cookie_header.lower()


@pytest.mark.asyncio
async def test_me_returns_user_when_auth_disabled(app_with_db, monkeypatch):
    """With AUTH_ENABLED=false, /me returns the synthetic dev context."""
    monkeypatch.setenv("AUTH_ENABLED", "false")
    transport = ASGITransport(app=app_with_db)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/v1/auth/me")
    assert resp.status_code == 200
    body = resp.json()
    assert body["tenant_id"]  # default tenant
    assert body["user_id"]


@pytest.mark.asyncio
async def test_logout_clears_cookie(app_with_db):
    transport = ASGITransport(app=app_with_db)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/v1/auth/logout")
    assert resp.status_code == 200
    cookie_header = resp.headers.get("set-cookie", "")
    # Either Max-Age=0 or expires in the past — both indicate deletion.
    assert "access_token=" in cookie_header
    assert "Max-Age=0" in cookie_header or "expires=" in cookie_header.lower()


@pytest.mark.asyncio
async def test_cookie_jwt_round_trip_with_auth_enabled(app_with_db, monkeypatch):
    """End-to-end: callback mints a cookie, /me reads it back."""
    monkeypatch.setenv("AUTH_ENABLED", "true")
    fake_token = {
        "userinfo": {
            "sub": "google-sub-rt",
            "email": "rt@acme.com",
            "name": "RT",
        },
    }

    with patch("src.api.auth_routes.oauth.create_client") as create_client:
        client_mock = MagicMock()
        client_mock.authorize_access_token = AsyncMock(return_value=fake_token)
        create_client.return_value = client_mock

        transport = ASGITransport(app=app_with_db)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
            follow_redirects=False,
        ) as client:
            cb = await client.get("/v1/auth/callback/google")
            assert cb.status_code == 302
            # Cookie is now in the httpx client jar
            me = await client.get("/v1/auth/me")

    assert me.status_code == 200
    body = me.json()
    assert body["email"] == "rt@acme.com"
    assert body["tenant_id"]
