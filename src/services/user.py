"""User + tenant provisioning service.

Handles the first-login flow: given an OAuth identity (provider + subject),
either return the existing user or create a fresh user with a personal
tenant. Email is treated as globally unique — a second OAuth identity
claiming an existing email is rejected, not silently merged.
"""

from __future__ import annotations

import re
import secrets
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.tenant import Tenant
from src.db.models.user import User

from .exceptions import IntegrityException


_SLUG_INVALID = re.compile(r"[^a-z0-9]+")


def _slug_from_email(email: str) -> str:
    local = email.split("@", 1)[0].lower()
    slug = _SLUG_INVALID.sub("-", local).strip("-")
    return slug or "user"


class UserService:
    """Provision and look up users tied to OAuth identities."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_oauth_identity(
        self, provider: str, subject: str
    ) -> Optional[User]:
        stmt = select(User).where(
            User.oauth_provider == provider,
            User.oauth_subject == subject,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert_oauth_user(
        self,
        *,
        provider: str,
        subject: str,
        email: str,
        name: Optional[str] = None,
    ) -> User:
        """Find the user for this OAuth identity, or create a new one.

        First-time users get a freshly minted personal tenant. Repeat logins
        update ``name`` and ``last_login_at``. Email collisions across
        identities raise ``IntegrityException`` — the caller should map this
        to 409 Conflict.
        """
        existing = await self.get_by_oauth_identity(provider, subject)
        now = datetime.now(timezone.utc)

        if existing is not None:
            if name and existing.name != name:
                existing.name = name
            existing.last_login_at = now
            await self.db.flush()
            return existing

        # Fresh user — create a personal tenant first.
        tenant = Tenant(
            id=f"tenant-{uuid.uuid4()}",
            name=name or email,
            slug=await self._unique_slug(_slug_from_email(email)),
        )
        self.db.add(tenant)
        try:
            await self.db.flush()
        except IntegrityError as e:
            raise IntegrityException(f"Failed to create tenant for {email}") from e

        user = User(
            id=f"user-{uuid.uuid4()}",
            tenant_id=tenant.id,
            email=email,
            name=name,
            oauth_provider=provider,
            oauth_subject=subject,
            role="member",
            last_login_at=now,
        )
        self.db.add(user)
        try:
            await self.db.flush()
        except IntegrityError as e:
            # Email or (provider, subject) clash — surface so the route can
            # return 409 instead of silently linking accounts.
            raise IntegrityException(
                f"User already exists with conflicting identity ({email})"
            ) from e
        return user

    async def _unique_slug(self, base: str) -> str:
        """Pick a tenant slug that does not collide. Appends a short suffix
        on collision (rare in practice — keeps URLs human-readable).
        """
        candidate = base
        for _ in range(5):
            existing = await self.db.execute(
                select(Tenant.id).where(Tenant.slug == candidate)
            )
            if existing.scalar_one_or_none() is None:
                return candidate
            candidate = f"{base}-{secrets.token_hex(3)}"
        return f"{base}-{secrets.token_hex(6)}"
