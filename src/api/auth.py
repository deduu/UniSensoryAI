"""JWT authentication for the UniSensoryAI API.

Provides JWT token creation, verification, and a FastAPI dependency
for protecting endpoints.

Usage::

    # In server.py
    from src.api.auth import get_current_user, create_access_token, AuthConfig

    @app.post("/v1/process_document")
    async def process_document(user: dict = Depends(get_current_user)):
        ...

Environment variables:
    AUTH_ENABLED: Set to "true" to require auth (default: "false").
    JWT_SECRET_KEY: Secret key for signing tokens.
    JWT_ALGORITHM: Algorithm (default: "HS256").
    JWT_EXPIRATION_MINUTES: Token expiration in minutes (default: 60).
"""

import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, Dict, Optional, Union

from fastapi import Cookie, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

# Security scheme
_security = HTTPBearer(auto_error=False)

# Seed tenant created by alembic migration 5ac699391b63 for backfill /
# pre-auth uploads. Real tenants come from the JWT once auth is enabled.
DEFAULT_TENANT_ID = os.getenv("DEFAULT_TENANT_ID", "default")

# User id used for the synthetic dev context when AUTH_ENABLED=false.
DEV_USER_ID = "dev-user"


class UserContext(BaseModel):
    """Typed identity for the current request.

    Built from the JWT payload (real auth) or as a synthetic dev value
    when ``AUTH_ENABLED=false``. Inject via ``Depends(get_user_context)``.
    """

    user_id: str = Field(..., description="Stable user identifier (JWT ``sub``).")
    tenant_id: str = Field(..., description="Tenant the user belongs to.")
    email: Optional[str] = Field(default=None, description="User email if available.")


def resolve_tenant_id(user: Union[UserContext, Dict[str, Any], None]) -> str:
    """Resolve the tenant_id for the current request.

    Accepts a ``UserContext``, a raw JWT-payload dict, or ``None`` (auth
    disabled). Falls back to ``DEFAULT_TENANT_ID`` when there is no user.
    Raises 401 if a dict payload is missing the ``tenant_id`` claim.
    """
    if user is None:
        return DEFAULT_TENANT_ID
    if isinstance(user, UserContext):
        return user.tenant_id
    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing tenant_id claim",
        )
    return str(tenant_id)


class AuthConfig:
    """Authentication configuration from environment variables."""

    @staticmethod
    def is_enabled() -> bool:
        """Check if authentication is enabled."""
        return os.getenv("AUTH_ENABLED", "false").lower() == "true"

    @staticmethod
    def get_secret_key() -> str:
        """Get the JWT secret key."""
        key = os.getenv("JWT_SECRET_KEY", "")
        if not key and AuthConfig.is_enabled():
            raise RuntimeError(
                "JWT_SECRET_KEY environment variable is required when AUTH_ENABLED=true"
            )
        return key

    @staticmethod
    def get_algorithm() -> str:
        """Get the JWT algorithm."""
        return os.getenv("JWT_ALGORITHM", "HS256")

    @staticmethod
    def get_expiration_minutes() -> int:
        """Get token expiration in minutes."""
        return int(os.getenv("JWT_EXPIRATION_MINUTES", "60"))


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a JWT access token.

    Args:
        data: Payload data (must include "sub" for subject).
        expires_delta: Custom expiration. Defaults to JWT_EXPIRATION_MINUTES.

    Returns:
        Encoded JWT string.
    """
    try:
        import jwt
    except ImportError:
        raise ImportError(
            "PyJWT package is required for authentication. "
            "Install it with: pip install PyJWT"
        )

    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=AuthConfig.get_expiration_minutes()
        )

    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})

    return jwt.encode(
        to_encode,
        AuthConfig.get_secret_key(),
        algorithm=AuthConfig.get_algorithm(),
    )


def verify_token(token: str) -> Dict[str, Any]:
    """Verify and decode a JWT token.

    Args:
        token: The JWT token string.

    Returns:
        Decoded payload dict.

    Raises:
        HTTPException: If token is invalid or expired.
    """
    try:
        import jwt
    except ImportError:
        raise ImportError("PyJWT package is required for authentication.")

    try:
        payload = jwt.decode(
            token,
            AuthConfig.get_secret_key(),
            algorithms=[AuthConfig.get_algorithm()],
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_security),
) -> Optional[Dict[str, Any]]:
    """FastAPI dependency that extracts and verifies the JWT from the request.

    When AUTH_ENABLED=false, returns None (all requests allowed).
    When AUTH_ENABLED=true, validates the Bearer token and returns the payload.

    Args:
        credentials: Extracted from Authorization header.

    Returns:
        Decoded JWT payload, or None if auth is disabled.

    Raises:
        HTTPException: 401 if auth is enabled and token is missing/invalid.
    """
    if not AuthConfig.is_enabled():
        return None

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Provide a Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return verify_token(credentials.credentials)


async def get_user_context(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_security),
    access_token: Annotated[Optional[str], Cookie()] = None,
) -> UserContext:
    """FastAPI dependency that always yields a ``UserContext``.

    When ``AUTH_ENABLED=false`` (local dev) returns a synthetic context
    scoped to ``DEFAULT_TENANT_ID``. When enabled, the JWT is read from
    the ``access_token`` HttpOnly cookie (preferred) or the
    ``Authorization: Bearer`` header (for API clients/CLIs). The token
    must carry ``sub`` and ``tenant_id`` claims; otherwise 401.
    """
    if not AuthConfig.is_enabled():
        return UserContext(user_id=DEV_USER_ID, tenant_id=DEFAULT_TENANT_ID)

    raw_token: Optional[str] = None
    if access_token:
        raw_token = access_token
    elif credentials is not None:
        raw_token = credentials.credentials

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = verify_token(raw_token)

    user_id = payload.get("sub")
    tenant_id = payload.get("tenant_id")
    if not user_id or not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing required claim (sub/tenant_id)",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return UserContext(
        user_id=str(user_id),
        tenant_id=str(tenant_id),
        email=payload.get("email"),
    )
