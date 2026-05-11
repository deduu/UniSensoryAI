"""End-to-end tenant isolation tests against in-memory SQLite.

Verifies that IngestionService and ChatService refuse to surface rows
that belong to a different tenant, even when the caller passes the
correct id. This is the core multi-tenancy guarantee — a query that
hits an id in another tenant must return None / empty.
"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool

from src.db.base import Base
from src.db.models.tenant import Tenant
from src.db.models import ingestion, document, chat, user  # noqa: F401 register tables
from src.services.ingestion import IngestionService
from src.services.chat import ChatService


@pytest_asyncio.fixture
async def db() -> AsyncSession:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        # Seed two tenants
        session.add_all([
            Tenant(id="t-A", name="Acme", slug="acme"),
            Tenant(id="t-B", name="Beta", slug="beta"),
        ])
        await session.commit()
        yield session
    await engine.dispose()


class TestIngestionTenantIsolation:
    @pytest.mark.asyncio
    async def test_list_jobs_excludes_other_tenant(self, db):
        service = IngestionService(db)
        await service.create_job("/file-a.pdf", tenant_id="t-A")
        await service.create_job("/file-b.pdf", tenant_id="t-B")
        await db.commit()

        jobs_a = await service.list_jobs(tenant_id="t-A")
        jobs_b = await service.list_jobs(tenant_id="t-B")

        assert len(jobs_a) == 1
        assert jobs_a[0].file_path == "/file-a.pdf"
        assert len(jobs_b) == 1
        assert jobs_b[0].file_path == "/file-b.pdf"

    @pytest.mark.asyncio
    async def test_get_by_id_returns_none_for_other_tenant(self, db):
        """A get_by_id for a job in tenant A scoped to tenant B returns None."""
        service = IngestionService(db)
        job = await service.create_job("/file.pdf", tenant_id="t-A")
        await db.commit()

        # Same id, wrong tenant => None (404 at endpoint layer)
        result = await service.get_by_id(
            job.id, raise_not_found=False, tenant_id="t-B"
        )
        assert result is None

        # Correct tenant => found
        result = await service.get_by_id(
            job.id, raise_not_found=False, tenant_id="t-A"
        )
        assert result is not None
        assert result.id == job.id

    @pytest.mark.asyncio
    async def test_get_by_id_without_tenant_scope_is_global(self, db):
        """Sanity: when tenant_id is omitted, get_by_id is global (backward compat)."""
        service = IngestionService(db)
        job = await service.create_job("/file.pdf", tenant_id="t-A")
        await db.commit()

        # No tenant_id passed => returns the row regardless. The tenant guard
        # is opt-in per call so background workers can still operate by job id.
        result = await service.get_by_id(job.id, raise_not_found=False)
        assert result is not None


class TestChatTenantIsolation:
    @pytest.mark.asyncio
    async def test_list_conversations_excludes_other_tenant(self, db):
        service = ChatService(db)
        await service.create_conversation(title="A1", tenant_id="t-A")
        await service.create_conversation(title="B1", tenant_id="t-B")
        await service.create_conversation(title="A2", tenant_id="t-A")
        await db.commit()

        convs_a = await service.list_conversations(tenant_id="t-A")
        titles_a = {c.title for c in convs_a}
        assert titles_a == {"A1", "A2"}

        convs_b = await service.list_conversations(tenant_id="t-B")
        assert {c.title for c in convs_b} == {"B1"}

    @pytest.mark.asyncio
    async def test_get_conversation_with_messages_other_tenant_is_none(self, db):
        service = ChatService(db)
        conv = await service.create_conversation(title="Secret", tenant_id="t-A")
        await db.commit()

        wrong = await service.get_conversation_with_messages(
            conv.id, tenant_id="t-B"
        )
        assert wrong is None

        right = await service.get_conversation_with_messages(
            conv.id, tenant_id="t-A"
        )
        assert right is not None
        assert right.title == "Secret"
