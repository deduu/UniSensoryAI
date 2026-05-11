"""Tests for Tenant and User ORM models."""

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool

from src.db.base import Base
from src.db.models.tenant import Tenant
from src.db.models.user import User
from src.db.models import ingestion, document, chat  # noqa: F401 register tables


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    """In-memory SQLite session for ORM tests."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


class TestTenant:
    @pytest.mark.asyncio
    async def test_create_tenant(self, session):
        tenant = Tenant(id="t-1", name="Acme Inc.", slug="acme")
        session.add(tenant)
        await session.commit()

        result = await session.execute(select(Tenant).where(Tenant.id == "t-1"))
        loaded = result.scalar_one()
        assert loaded.name == "Acme Inc."
        assert loaded.slug == "acme"
        assert loaded.created_at is not None

    @pytest.mark.asyncio
    async def test_tenant_slug_unique(self, session):
        session.add(Tenant(id="t-a", name="A", slug="shared"))
        await session.commit()
        session.add(Tenant(id="t-b", name="B", slug="shared"))
        with pytest.raises(IntegrityError):
            await session.commit()


class TestUser:
    @pytest.mark.asyncio
    async def test_create_user_under_tenant(self, session):
        tenant = Tenant(id="t-1", name="Acme", slug="acme")
        session.add(tenant)
        await session.flush()

        user = User(
            id="u-1",
            tenant_id="t-1",
            email="alice@acme.com",
            name="Alice",
            oauth_provider="google",
            oauth_subject="google-sub-123",
        )
        session.add(user)
        await session.commit()

        loaded = (
            await session.execute(select(User).where(User.id == "u-1"))
        ).scalar_one()
        assert loaded.tenant_id == "t-1"
        assert loaded.email == "alice@acme.com"
        assert loaded.oauth_provider == "google"
        assert loaded.role == "member"

    @pytest.mark.asyncio
    async def test_user_email_unique(self, session):
        session.add(Tenant(id="t-1", name="A", slug="a"))
        await session.flush()
        session.add(
            User(
                id="u-1",
                tenant_id="t-1",
                email="dup@x.com",
                name="A",
                oauth_provider="google",
                oauth_subject="s1",
            )
        )
        await session.commit()
        session.add(
            User(
                id="u-2",
                tenant_id="t-1",
                email="dup@x.com",
                name="B",
                oauth_provider="github",
                oauth_subject="s2",
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()

    @pytest.mark.asyncio
    async def test_user_oauth_identity_unique(self, session):
        """(oauth_provider, oauth_subject) must be unique together."""
        session.add(Tenant(id="t-1", name="A", slug="a"))
        await session.flush()
        session.add(
            User(
                id="u-1",
                tenant_id="t-1",
                email="a@x.com",
                name="A",
                oauth_provider="google",
                oauth_subject="same-sub",
            )
        )
        await session.commit()
        session.add(
            User(
                id="u-2",
                tenant_id="t-1",
                email="b@x.com",
                name="B",
                oauth_provider="google",
                oauth_subject="same-sub",
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()

    @pytest.mark.asyncio
    async def test_user_tenant_relationship(self, session):
        tenant = Tenant(id="t-1", name="A", slug="a")
        session.add(tenant)
        await session.flush()
        session.add(
            User(
                id="u-1",
                tenant_id="t-1",
                email="a@x.com",
                name="A",
                oauth_provider="google",
                oauth_subject="s1",
            )
        )
        await session.commit()

        from sqlalchemy.orm import selectinload

        loaded_tenant = (
            await session.execute(
                select(Tenant)
                .where(Tenant.id == "t-1")
                .options(selectinload(Tenant.users))
            )
        ).scalar_one()
        assert len(loaded_tenant.users) == 1
        assert loaded_tenant.users[0].email == "a@x.com"
