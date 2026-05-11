"""OAuth login routes (Google + GitHub).

Flow:

1. Frontend renders ``<a href="/v1/auth/login/{provider}">``.
2. Backend redirects to the provider's authorize URL.
3. Provider redirects back to ``/v1/auth/callback/{provider}`` with a code.
4. Backend exchanges the code for a token, fetches the user identity,
   upserts the local ``User``, mints a JWT, sets it as an HttpOnly cookie,
   and 302's to ``FRONTEND_URL``.
5. Subsequent requests from the browser include the cookie; the
   ``get_user_context`` dependency reads it to identify the caller.

The token transport is a cookie (HttpOnly, SameSite=Lax). The browser
never sees the raw JWT, so XSS in the SPA cannot steal it.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional
from urllib.parse import urljoin

from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse

from src.api.auth import (
    AuthConfig,
    UserContext,
    create_access_token,
    get_user_context,
)
from src.db.session import get_db
from src.services.exceptions import IntegrityException
from src.services.user import UserService


logger = logging.getLogger(__name__)


COOKIE_NAME = "access_token"
PROVIDERS = ("google", "github")


def _frontend_url() -> str:
    return os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")


def _redirect_base() -> str:
    # Used to construct the absolute callback URL passed to the provider.
    # Falls back to the request's own origin in the route if unset.
    return os.getenv("OAUTH_REDIRECT_BASE_URL", "").rstrip("/")


def _cookie_secure() -> bool:
    # SameSite=Lax + Secure in production; allow non-HTTPS in dev.
    return os.getenv("COOKIE_SECURE", "false").lower() == "true"


def _build_oauth() -> OAuth:
    """Construct and configure the Authlib OAuth registry.

    Reads provider client ids/secrets from the environment. Providers
    without credentials configured are still registered but will reject
    the flow at runtime (the login endpoint surfaces a 503 in that case).
    """
    oauth = OAuth()
    oauth.register(
        name="google",
        client_id=os.getenv("OAUTH_GOOGLE_CLIENT_ID", ""),
        client_secret=os.getenv("OAUTH_GOOGLE_CLIENT_SECRET", ""),
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )
    oauth.register(
        name="github",
        client_id=os.getenv("OAUTH_GITHUB_CLIENT_ID", ""),
        client_secret=os.getenv("OAUTH_GITHUB_CLIENT_SECRET", ""),
        api_base_url="https://api.github.com/",
        access_token_url="https://github.com/login/oauth/access_token",
        authorize_url="https://github.com/login/oauth/authorize",
        client_kwargs={"scope": "read:user user:email"},
    )
    return oauth


oauth = _build_oauth()
router = APIRouter(prefix="/v1/auth", tags=["auth"])


def _callback_url(request: Request, provider: str) -> str:
    base = _redirect_base() or str(request.base_url).rstrip("/")
    return urljoin(base + "/", f"v1/auth/callback/{provider}")


def _provider_configured(provider: str) -> bool:
    client_id = os.getenv(f"OAUTH_{provider.upper()}_CLIENT_ID", "")
    secret = os.getenv(f"OAUTH_{provider.upper()}_CLIENT_SECRET", "")
    return bool(client_id and secret)


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=_cookie_secure(),
        samesite="lax",
        max_age=AuthConfig.get_expiration_minutes() * 60,
        path="/",
    )


async def _extract_identity(provider: str, client: Any, token: dict) -> dict:
    """Normalize provider-specific userinfo into a flat dict.

    Returns ``{"subject": str, "email": str, "name": str | None}``. Raises
    ``HTTPException(400)`` if the provider does not return enough info to
    identify the user (no email, no subject).
    """
    if provider == "google":
        info = token.get("userinfo")
        if not info:
            # Older Authlib versions: parse the id_token explicitly.
            info = await client.parse_id_token(token, nonce=None)
        subject = info.get("sub")
        email = info.get("email")
        name = info.get("name") or info.get("given_name")
    elif provider == "github":
        resp = await client.get("user", token=token)
        info = resp.json()
        subject = str(info.get("id", ""))
        email = info.get("email")
        name = info.get("name") or info.get("login")
        if not email:
            # GitHub hides primary email unless user marks it public.
            emails_resp = await client.get("user/emails", token=token)
            for entry in emails_resp.json() or []:
                if entry.get("primary") and entry.get("verified"):
                    email = entry.get("email")
                    break
    else:  # pragma: no cover — guarded earlier
        raise HTTPException(status_code=400, detail=f"Unsupported provider {provider!r}")

    if not subject or not email:
        raise HTTPException(
            status_code=400,
            detail=f"Provider {provider!r} did not return an email or subject",
        )
    return {"subject": str(subject), "email": str(email), "name": name}


@router.get("/login/{provider}")
async def login(provider: str, request: Request) -> Response:
    if provider not in PROVIDERS:
        raise HTTPException(status_code=404, detail=f"Unknown provider {provider!r}")
    if not _provider_configured(provider):
        raise HTTPException(
            status_code=503,
            detail=f"OAuth provider {provider!r} is not configured on this server",
        )
    client = oauth.create_client(provider)
    redirect_uri = _callback_url(request, provider)
    return await client.authorize_redirect(request, redirect_uri)


@router.get("/callback/{provider}")
async def callback(provider: str, request: Request, db=Depends(get_db)) -> Response:
    if provider not in PROVIDERS:
        raise HTTPException(status_code=404, detail=f"Unknown provider {provider!r}")
    client = oauth.create_client(provider)
    try:
        token = await client.authorize_access_token(request)
    except OAuthError as e:
        logger.warning(f"OAuth callback failed for {provider}: {e}")
        raise HTTPException(status_code=400, detail=f"OAuth error: {e.description or e.error}")

    identity = await _extract_identity(provider, client, token)

    service = UserService(db)
    try:
        user = await service.upsert_oauth_user(
            provider=provider,
            subject=identity["subject"],
            email=identity["email"],
            name=identity.get("name"),
        )
        await db.commit()
    except IntegrityException as e:
        await db.rollback()
        raise HTTPException(status_code=409, detail=str(e))

    jwt_token = create_access_token({
        "sub": user.id,
        "tenant_id": user.tenant_id,
        "email": user.email,
    })

    response = RedirectResponse(url=_frontend_url(), status_code=302)
    _set_session_cookie(response, jwt_token)
    return response


@router.get("/me")
async def me(user: UserContext = Depends(get_user_context)) -> JSONResponse:
    return JSONResponse(content={
        "user_id": user.user_id,
        "tenant_id": user.tenant_id,
        "email": user.email,
    })


@router.post("/logout")
async def logout() -> Response:
    response = JSONResponse(content={"detail": "Logged out"})
    response.delete_cookie(COOKIE_NAME, path="/")
    return response
