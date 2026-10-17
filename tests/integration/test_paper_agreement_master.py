"""Real async SQLite persistence checks, independent of live infrastructure."""

from collections.abc import AsyncIterator
from datetime import date

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy import event, select
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.api.auth import UserContext, get_user_context
from src.api.paper_routes import get_paper_db, router
from src.db.base import Base
from src.db.models.agreement import Agreement
from src.db.models.agreement_approval import AgreementApproval
from src.db.models.agreement_version import AgreementVersion as AgreementVersionRow
from src.db.models.tenant import Tenant
from src.db.models.user import User
from src.paper.contracts import (
    AgreementActor,
    AgreementDraft,
    AgreementIdentity,
    AgreementLookup,
    ApprovalDecision,
)
from src.paper.errors import AgreementMasterError
from src.paper.schemas import RentAgreementSchema
from src.services.agreement_repository import SqlAlchemyAgreementRepository


@pytest_asyncio.fixture
async def db() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)

    @event.listens_for(engine.sync_engine, "connect")
    def enable_foreign_keys(connection: object, _: object) -> None:
        # Python 3.10/3.11 SQLite legacy transaction mode otherwise releases
        # a SAVEPOINT before a real BEGIN, defeating the rollback assertion.
        connection.isolation_level = None  # type: ignore[attr-defined]
        cursor = connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    @event.listens_for(engine.sync_engine, "begin")
    def begin_transaction(connection: Connection) -> None:
        connection.exec_driver_sql("BEGIN")

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    async with maker() as session:
        session.add_all(
            [Tenant(id="tenant-a", name="A", slug="a"), Tenant(id="tenant-b", name="B", slug="b")]
        )
        await session.commit()
        yield session
    await engine.dispose()


def _identity() -> AgreementIdentity:
    return AgreementIdentity(vendor_id="vendor-1", store_id="store-1", contract_number="RA-1")


def _draft(*, amount: str = "1000000.00") -> AgreementDraft:
    return AgreementDraft(
        terms=RentAgreementSchema(
            vendor_name="Landlord",
            vendor_id="vendor-1",
            store_id="store-1",
            contract_number="RA-1",
            lease_start_date="2026-01-01",
            lease_end_date="2026-12-31",
            payment_schedule="Monthly",
            rent_type="fixed",
            currency="IDR",
            fixed_rent=amount,
        ),
        effective_from=date(2026, 1, 1),
        effective_to=date(2026, 12, 31),
        source_document_ids=("source-1",),
        change_reason="New reviewed terms",
    )


def _actor(*, tenant_id: str = "tenant-a", approve: bool = False) -> AgreementActor:
    return AgreementActor(tenant_id=tenant_id, user_id="accountant-1", can_approve=approve)


def _decision() -> ApprovalDecision:
    return ApprovalDecision(
        classification="psak73", rule_set_id="rent", rule_set_version="2026.1", reason="Reviewed"
    )


@pytest.mark.asyncio
async def test_drafts_stay_private_and_approved_snapshot_roundtrips(db: AsyncSession) -> None:
    repository = SqlAlchemyAgreementRepository(db)
    created = await repository.create(identity=_identity(), draft=_draft(), actor=_actor())
    assert created.version_number == 1
    assert created.approval is None
    assert created.created_at.tzinfo is not None
    assert (
        await repository.find_approved(
            tenant_id="tenant-a",
            lookup=AgreementLookup(identity=_identity(), as_of=date(2026, 6, 1)),
        )
        is None
    )
    approved = await repository.approve(
        agreement_id=created.agreement_id,
        version_number=1,
        decision=_decision(),
        actor=_actor(approve=True),
    )
    await db.commit()
    db.expire_all()
    reloaded = await repository.get_version(
        tenant_id="tenant-a", agreement_id=created.agreement_id, version_number=1
    )
    assert reloaded is not None
    assert reloaded.draft == created.draft
    assert reloaded.approval == approved.approval
    assert reloaded.approval is not None
    assert reloaded.approval.approved_at.tzinfo is not None
    assert reloaded.approval.rule_set_version == "2026.1"


@pytest.mark.asyncio
async def test_new_draft_preserves_approved_reference_and_old_snapshot(db: AsyncSession) -> None:
    repository = SqlAlchemyAgreementRepository(db)
    first = await repository.create(identity=_identity(), draft=_draft(), actor=_actor())
    await repository.approve(
        agreement_id=first.agreement_id,
        version_number=1,
        decision=_decision(),
        actor=_actor(approve=True),
    )
    second = await repository.append(
        agreement_id=first.agreement_id,
        draft=_draft(amount="2000000.00"),
        expected_version=1,
        actor=_actor(),
    )
    await db.commit()
    found = await repository.find_approved(
        tenant_id="tenant-a", lookup=AgreementLookup(identity=_identity(), as_of=date(2026, 6, 1))
    )
    assert found is not None and found.version_number == 1
    versions = await repository.list_versions(tenant_id="tenant-a", agreement_id=first.agreement_id)
    assert [version.version_number for version in versions] == [2, 1]
    assert versions[0].draft == second.draft
    assert versions[1].draft == first.draft
    await repository.approve(
        agreement_id=first.agreement_id,
        version_number=2,
        decision=_decision(),
        actor=_actor(approve=True),
    )
    newest = await repository.find_approved(
        tenant_id="tenant-a", lookup=AgreementLookup(identity=_identity(), as_of=date(2026, 6, 1))
    )
    assert newest is not None and newest.version_number == 2
    assert (
        await repository.find_approved(
            tenant_id="tenant-a",
            lookup=AgreementLookup(identity=_identity(), as_of=date(2027, 1, 1)),
        )
        is None
    )


@pytest.mark.asyncio
async def test_stale_updates_and_repeat_approval_conflict_without_breaking_session(
    db: AsyncSession,
) -> None:
    repository = SqlAlchemyAgreementRepository(db)
    first = await repository.create(identity=_identity(), draft=_draft(), actor=_actor())
    await repository.append(
        agreement_id=first.agreement_id, draft=_draft(), expected_version=1, actor=_actor()
    )
    for operation in (
        repository.append(
            agreement_id=first.agreement_id, draft=_draft(), expected_version=1, actor=_actor()
        ),
        repository.approve(
            agreement_id=first.agreement_id,
            version_number=1,
            decision=_decision(),
            actor=_actor(approve=True),
        ),
    ):
        with pytest.raises(AgreementMasterError) as caught:
            await operation
        assert caught.value.code == "conflict"
    await repository.approve(
        agreement_id=first.agreement_id,
        version_number=2,
        decision=_decision(),
        actor=_actor(approve=True),
    )
    with pytest.raises(AgreementMasterError) as caught:
        await repository.approve(
            agreement_id=first.agreement_id,
            version_number=2,
            decision=_decision(),
            actor=_actor(approve=True),
        )
    assert caught.value.code == "conflict"
    await db.commit()
    assert (
        len(await repository.list_versions(tenant_id="tenant-a", agreement_id=first.agreement_id))
        == 2
    )


@pytest.mark.asyncio
async def test_all_operations_are_tenant_scoped(db: AsyncSession) -> None:
    repository = SqlAlchemyAgreementRepository(db)
    first = await repository.create(identity=_identity(), draft=_draft(), actor=_actor())
    other = await repository.create(
        identity=_identity(), draft=_draft(), actor=_actor(tenant_id="tenant-b")
    )
    assert first.agreement_id != other.agreement_id
    assert (
        await repository.get_version(
            tenant_id="tenant-b", agreement_id=first.agreement_id, version_number=1
        )
        is None
    )
    assert (
        await repository.list_versions(tenant_id="tenant-b", agreement_id=first.agreement_id) == ()
    )
    with pytest.raises(AgreementMasterError):
        await repository.append(
            agreement_id=first.agreement_id,
            draft=_draft(),
            expected_version=1,
            actor=_actor(tenant_id="tenant-b"),
        )
    with pytest.raises(AgreementMasterError):
        await repository.approve(
            agreement_id=first.agreement_id,
            version_number=1,
            decision=_decision(),
            actor=_actor(tenant_id="tenant-b", approve=True),
        )
    await db.commit()


@pytest.mark.asyncio
async def test_duplicate_identity_conflict_leaves_original_transaction_usable(
    db: AsyncSession,
) -> None:
    repository = SqlAlchemyAgreementRepository(db)
    first = await repository.create(identity=_identity(), draft=_draft(), actor=_actor())
    with pytest.raises(AgreementMasterError) as caught:
        await repository.create(identity=_identity(), draft=_draft(), actor=_actor())
    assert caught.value.code == "conflict"
    await db.commit()
    assert (
        await repository.get_version(
            tenant_id="tenant-a", agreement_id=first.agreement_id, version_number=1
        )
        is not None
    )


@pytest.mark.asyncio
async def test_composite_foreign_key_rejects_cross_tenant_snapshot(db: AsyncSession) -> None:
    repository = SqlAlchemyAgreementRepository(db)
    first = await repository.create(identity=_identity(), draft=_draft(), actor=_actor())
    await db.commit()
    with pytest.raises(IntegrityError):
        async with db.begin_nested():
            db.add(
                AgreementVersionRow(
                    tenant_id="tenant-b",
                    agreement_id=first.agreement_id,
                    version_number=2,
                    effective_from=date(2026, 1, 1),
                    effective_to=date(2026, 12, 31),
                    draft=_draft().model_dump(mode="json"),
                    created_by="author",
                )
            )
            await db.flush()


@pytest.mark.asyncio
async def test_repository_does_not_commit_or_allow_version_mutation(db: AsyncSession) -> None:
    repository = SqlAlchemyAgreementRepository(db)
    created = await repository.create(identity=_identity(), draft=_draft(), actor=_actor())
    await db.rollback()
    assert (
        await repository.get_version(
            tenant_id="tenant-a", agreement_id=created.agreement_id, version_number=1
        )
        is None
    )
    next_version = await repository.create(identity=_identity(), draft=_draft(), actor=_actor())
    await db.commit()
    row = (
        await db.execute(
            select(AgreementVersionRow).where(
                AgreementVersionRow.agreement_id == next_version.agreement_id
            )
        )
    ).scalar_one()
    row.draft = {"overwritten": True}
    with pytest.raises(ValueError, match="immutable"):
        await db.flush()
    await db.rollback()
    assert len((await db.execute(select(Agreement))).scalars().all()) == 1
    assert len((await db.execute(select(AgreementApproval))).scalars().all()) == 0


@pytest.mark.asyncio
async def test_approved_effective_lookup_respects_both_inclusive_boundaries(
    db: AsyncSession,
) -> None:
    repository = SqlAlchemyAgreementRepository(db)
    first = await repository.create(identity=_identity(), draft=_draft(), actor=_actor())
    await repository.approve(
        agreement_id=first.agreement_id,
        version_number=1,
        decision=_decision(),
        actor=_actor(approve=True),
    )
    later_draft = _draft(amount="2000000.00").model_copy(
        update={"effective_from": date(2026, 7, 1)}
    )
    await repository.append(
        agreement_id=first.agreement_id, draft=later_draft, expected_version=1, actor=_actor()
    )
    await repository.approve(
        agreement_id=first.agreement_id,
        version_number=2,
        decision=_decision(),
        actor=_actor(approve=True),
    )
    for business_date, expected in (
        (date(2026, 1, 1), 1),
        (date(2026, 6, 30), 1),
        (date(2026, 7, 1), 2),
        (date(2026, 12, 31), 2),
    ):
        found = await repository.find_approved(
            tenant_id="tenant-a", lookup=AgreementLookup(identity=_identity(), as_of=business_date)
        )
        assert found is not None and found.version_number == expected
    assert (
        await repository.find_approved(
            tenant_id="tenant-a",
            lookup=AgreementLookup(identity=_identity(), as_of=date(2025, 12, 31)),
        )
        is None
    )


@pytest.mark.asyncio
async def test_expired_approved_amendment_does_not_revive_superseded_terms(
    db: AsyncSession,
) -> None:
    repository = SqlAlchemyAgreementRepository(db)
    first = await repository.create(identity=_identity(), draft=_draft(), actor=_actor())
    await repository.approve(
        agreement_id=first.agreement_id,
        version_number=1,
        decision=_decision(),
        actor=_actor(approve=True),
    )
    ending_amendment = _draft(amount="2000000.00").model_copy(
        update={"effective_from": date(2026, 7, 1), "effective_to": date(2026, 9, 30)}
    )
    await repository.append(
        agreement_id=first.agreement_id,
        draft=ending_amendment,
        expected_version=1,
        actor=_actor(),
    )
    await repository.approve(
        agreement_id=first.agreement_id,
        version_number=2,
        decision=_decision(),
        actor=_actor(approve=True),
    )
    await db.commit()
    before_amendment = await repository.find_approved(
        tenant_id="tenant-a",
        lookup=AgreementLookup(identity=_identity(), as_of=date(2026, 6, 30)),
    )
    assert before_amendment is not None and before_amendment.version_number == 1
    amendment_end = await repository.find_approved(
        tenant_id="tenant-a",
        lookup=AgreementLookup(identity=_identity(), as_of=date(2026, 9, 30)),
    )
    assert amendment_end is not None and amendment_end.version_number == 2
    assert (
        await repository.find_approved(
            tenant_id="tenant-a",
            lookup=AgreementLookup(identity=_identity(), as_of=date(2026, 10, 1)),
        )
        is None
    )


@pytest.mark.asyncio
async def test_approval_and_business_identity_cannot_be_mutated(db: AsyncSession) -> None:
    repository = SqlAlchemyAgreementRepository(db)
    version = await repository.create(identity=_identity(), draft=_draft(), actor=_actor())
    await repository.approve(
        agreement_id=version.agreement_id,
        version_number=1,
        decision=_decision(),
        actor=_actor(approve=True),
    )
    await db.commit()
    approval = (await db.execute(select(AgreementApproval))).scalar_one()
    approval.decision = {"classification": "non_psak73"}
    with pytest.raises(ValueError, match="immutable"):
        await db.flush()
    await db.rollback()
    header = (await db.execute(select(Agreement))).scalar_one()
    header.contract_number = "rewritten-identity"
    with pytest.raises(ValueError, match="immutable"):
        await db.flush()
    await db.rollback()


@pytest.mark.asyncio
async def test_http_agreement_master_roundtrip_with_real_authorization_and_storage(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("PAPER_CONFIG_PATH", raising=False)
    db.add_all(
        [
            User(
                id="accountant-a",
                tenant_id="tenant-a",
                email="accountant-a@example.test",
                oauth_provider="test",
                oauth_subject="accountant-a",
                role="accountant",
            ),
            User(
                id="member-b",
                tenant_id="tenant-b",
                email="member-b@example.test",
                oauth_provider="test",
                oauth_subject="member-b",
                role="member",
            ),
        ]
    )
    await db.commit()
    app = FastAPI()
    app.include_router(router)
    current_user = UserContext(user_id="accountant-a", tenant_id="tenant-a")

    async def provide_session() -> AsyncIterator[AsyncSession]:
        yield db

    async def provide_user() -> UserContext:
        return current_user

    app.dependency_overrides[get_paper_db] = provide_session
    app.dependency_overrides[get_user_context] = provide_user
    lookup = {**_identity().model_dump(), "as_of": "2026-06-01"}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://paper.test"
    ) as client:
        created = await client.post(
            "/v1/paper/agreements",
            json={"identity": _identity().model_dump(), "draft": _draft().model_dump(mode="json")},
        )
        assert created.status_code == 201
        first = created.json()
        assert first["status"] == "draft"
        assert first["created_by"] == "accountant-a"
        assert first["draft"]["schema_id"] == "paper.rent_agreement"
        assert first["draft"]["schema_version"] == "1"
        assert first["draft"]["extraction_warnings"] == []
        before_approval = await client.get("/v1/paper/agreements/approved", params=lookup)
        assert before_approval.status_code == 404

        approved = await client.post(
            f"/v1/paper/agreements/{first['agreement_id']}/versions/1/approval",
            json=_decision().model_dump(mode="json"),
        )
        assert approved.status_code == 200
        authoritative = approved.json()
        assert authoritative["status"] == "approved"
        assert authoritative["approval"]["approved_by"] == "accountant-a"
        assert authoritative["approval"]["classification"] == "psak73"
        assert authoritative["approval"]["rule_set_id"] == "rent"
        assert authoritative["approval"]["rule_set_version"] == "2026.1"
        reference = await client.get("/v1/paper/agreements/approved", params=lookup)
        assert reference.status_code == 200
        assert reference.json() == authoritative

        revised = await client.post(
            f"/v1/paper/agreements/{first['agreement_id']}/versions",
            json={
                "expected_version": 1,
                "draft": _draft(amount="2000000.00").model_dump(mode="json"),
            },
        )
        assert revised.status_code == 201
        assert revised.json()["version_number"] == 2
        assert revised.json()["status"] == "draft"
        reference_with_new_draft = await client.get("/v1/paper/agreements/approved", params=lookup)
        assert reference_with_new_draft.status_code == 200
        assert reference_with_new_draft.json() == authoritative

        current_user = UserContext(user_id="member-b", tenant_id="tenant-b")
        other_tenant = await client.get("/v1/paper/agreements/approved", params=lookup)
        assert other_tenant.status_code == 404
