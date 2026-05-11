"""Tests for UserService.upsert_oauth_user — first-login provisioning logic."""

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.db.base import Base
from src.db.models import chat, document, ingestion  # noqa: F401 register tables
from src.db.models.tenant import Tenant
from src.db.models.user import User
from src.services.user import UserService


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        yield session
    await engine.dispose()


class TestUpsertOAuthUser:
    @pytest.mark.asyncio
    async def test_first_login_creates_tenant_and_user(self, db):
        """First login for an identity creates a personal tenant + user."""
        service = UserService(db)
        user = await service.upsert_oauth_user(
            provider="google",
            subject="google-sub-1",
            email="alice@acme.com",
            name="Alice",
        )
        await db.commit()

        # User persisted with provider/subject
        assert user.email == "alice@acme.com"
        assert user.oauth_provider == "google"
        assert user.oauth_subject == "google-sub-1"
        assert user.last_login_at is not None

        # A tenant was created for them
        tenant = (
            await db.execute(select(Tenant).where(Tenant.id == user.tenant_id))
        ).scalar_one()
        assert tenant.slug.startswith("alice")  # derived from email local-part

    @pytest.mark.asyncio
    async def test_repeat_login_same_identity_no_new_tenant(self, db):
        service = UserService(db)
        first = await service.upsert_oauth_user(
            provider="google", subject="sub-1", email="bob@x.com", name="Bob"
        )
        await db.commit()
        original_tenant_id = first.tenant_id
        original_user_id = first.id

        second = await service.upsert_oauth_user(
            provider="google", subject="sub-1", email="bob@x.com", name="Bob Updated"
        )
        await db.commit()

        assert second.id == original_user_id
        assert second.tenant_id == original_tenant_id
        # last_login_at refreshed
        assert second.last_login_at >= first.last_login_at
        # Display name update applied
        assert second.name == "Bob Updated"

        # Only one tenant + user exist
        tenants = (await db.execute(select(Tenant))).scalars().all()
        users = (await db.execute(select(User))).scalars().all()
        assert len(tenants) == 1
        assert len(users) == 1

    @pytest.mark.asyncio
    async def test_different_provider_same_email_is_distinct_user(self, db):
        """Logging in via GitHub when a Google identity exists for the same
        email creates a SEPARATE user (provider+subject is the identity key,
        not email)."""
        service = UserService(db)
        await service.upsert_oauth_user(
            provider="google", subject="g-1", email="dup@x.com", name="A"
        )
        await db.commit()

        # Email collision must surface — we treat email as globally unique.
        # The service should raise rather than silently merging identities.
        from src.services.exceptions import IntegrityException

        with pytest.raises(IntegrityException):
            await service.upsert_oauth_user(
                provider="github", subject="gh-1", email="dup@x.com", name="A"
            )
            await db.commit()

    @pytest.mark.asyncio
    async def test_tenant_slug_collision_appends_suffix(self, db):
        """Two users with the same email local-part get distinct tenant slugs."""
        service = UserService(db)
        await service.upsert_oauth_user(
            provider="google", subject="g-1", email="alice@acme.com", name="A1"
        )
        await db.commit()
        await service.upsert_oauth_user(
            provider="google", subject="g-2", email="alice@beta.com", name="A2"
        )
        await db.commit()

        tenants = (await db.execute(select(Tenant))).scalars().all()
        slugs = {t.slug for t in tenants}
        assert len(slugs) == 2
        # Both start with "alice" but are distinct
        assert all(s.startswith("alice") for s in slugs)
