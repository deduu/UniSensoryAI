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
from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

# Security scheme
_security = HTTPBearer(auto_error=False)


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
