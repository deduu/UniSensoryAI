"""Durable PAPER invoice cases tested on isolated async SQLite."""

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import event, select
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.db.base import Base
from src.db.models.invoice_case import InvoiceCase
from src.db.models.invoice_case_decision import InvoiceCaseDecision
from src.db.models.invoice_case_version import InvoiceCaseVersion as InvoiceCaseVersionRow
from src.db.models.invoice_duplicate_claim import InvoiceDuplicateClaim
from src.db.models.tenant import Tenant
from src.paper.contracts import AgreementActor, AgreementIdentity
from src.paper.errors import AgreementMasterError
from src.paper.reconciliation.contracts import (
    AgreementReference,
    APDecision,
    InvoiceCaseVersion,
    InvoicePackage,
    ReconciliationAssessment,
    RentInvoiceDocument,
)
from src.paper.schemas import RentInvoiceSchema
from src.services.invoice_case_repository import SqlAlchemyInvoiceCaseRepository


def _installment_package(number: str, installment: str = "stage-1") -> InvoicePackage:
    body = _package().model_dump(mode="json")
    body["invoice"]["fields"].update(invoice_number=number, installment_id=installment)
    return InvoicePackage.model_validate(body)


def _installment_assessment(
    *, outcome: str = "matched", version: int = 1
) -> ReconciliationAssessment:
    body = _assessment().model_dump(mode="json")
    body["outcome"] = outcome
    body["agreement_reference"] = AgreementReference(
        agreement_id="agreement-1", version_number=version, classification="psak73"
    ).model_dump(mode="json")
    return ReconciliationAssessment.model_validate(body)


@pytest.mark.asyncio
async def test_installment_claim_blocks_different_invoice_number_across_approved_versions(
    db: AsyncSession,
) -> None:
    from src.paper.reconciliation.fingerprints import duplicate_key, installment_duplicate_key

    repo = SqlAlchemyInvoiceCaseRepository(db)
    first_package = _installment_package("ADVANCE-1")
    next_package = _installment_package("DIFFERENT-INVOICE")
    first = await repo.create(
        package=first_package,
        assessment=_installment_assessment(),
        duplicate_key=duplicate_key(first_package),
        actor=_actor(),
    )
    duplicate = await repo.create(
        package=next_package,
        assessment=_installment_assessment(version=2),
        duplicate_key=duplicate_key(next_package),
        actor=_actor(),
    )
    assert duplicate_key(first_package) != duplicate_key(next_package)
    assert installment_duplicate_key(first_package) == installment_duplicate_key(next_package)
    assert duplicate.duplicate_of == first.case_id
    assert duplicate.status == "duplicate"
    with pytest.raises(AgreementMasterError):
        await repo.decide(
            case_id=duplicate.case_id,
            expected_version=1,
            decision=APDecision(action="approve", reason="Must remain blocked"),
            actor=_actor(approve=True),
        )


@pytest.mark.asyncio
async def test_duplicate_invoice_loser_does_not_reserve_another_installment(
    db: AsyncSession,
) -> None:
    from src.paper.reconciliation.fingerprints import duplicate_key

    repo = SqlAlchemyInvoiceCaseRepository(db)
    saved = []
    for number, installment in (("ONE", "stage-1"), ("ONE", "stage-2"), ("TWO", "stage-2")):
        body = _installment_package(number, installment)
        saved.append(
            await repo.create(
                package=body,
                assessment=_installment_assessment(),
                duplicate_key=duplicate_key(body),
                actor=_actor(),
            )
        )
    assert saved[1].duplicate_of == saved[0].case_id
    assert saved[2].duplicate_of is None


@pytest.mark.asyncio
async def test_installment_claims_are_tenant_scoped_and_reused_by_case_revisions(
    db: AsyncSession,
) -> None:
    from src.paper.reconciliation.fingerprints import duplicate_key

    repo = SqlAlchemyInvoiceCaseRepository(db)
    body = _installment_package("ONE")
    first = await repo.create(
        package=body,
        assessment=_installment_assessment(),
        duplicate_key=duplicate_key(body),
        actor=_actor(),
    )
    corrected = _installment_package("CORRECTED-NUMBER")
    revised = await repo.append(
        case_id=first.case_id,
        package=corrected,
        assessment=_installment_assessment(version=2),
        duplicate_key=duplicate_key(corrected),
        expected_version=1,
        actor=_actor(),
    )
    other = await repo.create(
        package=body,
        assessment=_installment_assessment(),
        duplicate_key=duplicate_key(body),
        actor=_actor(tenant="tenant-b"),
    )
    assert revised.duplicate_of is None
    assert other.duplicate_of is None


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["incomplete", "mismatched"])
async def test_ineligible_assessments_do_not_reserve_installments(
    db: AsyncSession,
    outcome: str,
) -> None:
    from src.paper.reconciliation.fingerprints import duplicate_key

    repo = SqlAlchemyInvoiceCaseRepository(db)
    for index, result in enumerate((outcome, "matched")):
        body = _installment_package(f"INVOICE-{index}")
        saved = await repo.create(
            package=body,
            assessment=_installment_assessment(outcome=result),
            duplicate_key=duplicate_key(body),
            actor=_actor(),
        )
        assert saved.duplicate_of is None


@pytest.mark.asyncio
async def test_both_invoice_and_installment_claims_rollback_with_case(db: AsyncSession) -> None:
    from src.paper.reconciliation.fingerprints import duplicate_key, installment_duplicate_key

    repo = SqlAlchemyInvoiceCaseRepository(db)
    body = _installment_package("ONE")
    await repo.create(
        package=body,
        assessment=_installment_assessment(),
        duplicate_key=duplicate_key(body),
        actor=_actor(),
    )
    await db.rollback()
    for key in (duplicate_key(body), installment_duplicate_key(body)):
        assert key is not None
        assert await repo.duplicate_owner(tenant_id="tenant-a", duplicate_key=key) is None


@pytest.mark.asyncio
async def test_rejecting_installment_preserves_its_claim_for_same_case_correction(
    db: AsyncSession,
) -> None:
    from src.paper.reconciliation.fingerprints import duplicate_key

    repo = SqlAlchemyInvoiceCaseRepository(db)
    first_body = _installment_package("ONE")
    first = await repo.create(
        package=first_body,
        assessment=_installment_assessment(),
        duplicate_key=duplicate_key(first_body),
        actor=_actor(),
    )
    await repo.decide(
        case_id=first.case_id,
        expected_version=1,
        decision=APDecision(action="reject", reason="Correct this case"),
        actor=_actor(approve=True),
    )
    next_body = _installment_package("TWO")
    second = await repo.create(
        package=next_body,
        assessment=_installment_assessment(),
        duplicate_key=duplicate_key(next_body),
        actor=_actor(),
    )
    assert second.duplicate_of == first.case_id


@pytest_asyncio.fixture
async def db() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)

    @event.listens_for(engine.sync_engine, "connect")
    def enable_fk(connection: object, _: object) -> None:
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


def _package(*, amount: str = "100.00", vendor_id: str = "vendor-1") -> InvoicePackage:
    return InvoicePackage(
        identity=AgreementIdentity(vendor_id=vendor_id, store_id="store-1", contract_number="RA-1"),
        invoice=RentInvoiceDocument(
            source_document_id="source-1",
            fields=RentInvoiceSchema(
                invoice_number="INV-1", total=amount, extensions={"batch": ["one"]}
            ),
        ),
    )


def _assessment() -> ReconciliationAssessment:
    return ReconciliationAssessment(
        outcome="matched",
        policy_id="paper",
        policy_version="1",
        policy_fingerprint="a" * 64,
        package_fingerprint="b" * 64,
    )


def _actor(*, tenant: str = "tenant-a", approve: bool = False) -> AgreementActor:
    return AgreementActor(tenant_id=tenant, user_id="accountant", can_approve=approve)


async def _create(
    repository: SqlAlchemyInvoiceCaseRepository, *, key: str | None = None, tenant: str = "tenant-a"
) -> InvoiceCaseVersion:
    return await repository.create(
        package=_package(), assessment=_assessment(), duplicate_key=key, actor=_actor(tenant=tenant)
    )


@pytest.mark.asyncio
async def test_case_roundtrip_is_durable_with_version_and_decision(db: AsyncSession) -> None:
    repo = SqlAlchemyInvoiceCaseRepository(db)
    first = await _create(repo)
    approved = await repo.decide(
        case_id=first.case_id,
        expected_version=1,
        decision=APDecision(action="approve", reason="Matched and checked"),
        actor=_actor(approve=True),
    )
    await db.commit()
    db.expire_all()
    found = await repo.get_version(tenant_id="tenant-a", case_id=first.case_id, version_number=1)
    assert found == approved
    assert found is not None and found.status == "approved"
    assert found.decision is not None and found.decision.decided_at.tzinfo is not None


@pytest.mark.asyncio
async def test_case_and_duplicate_claim_rollback_belong_to_caller(db: AsyncSession) -> None:
    repo = SqlAlchemyInvoiceCaseRepository(db)
    first = await _create(repo, key="a" * 64)
    await db.rollback()
    assert (
        await repo.get_version(tenant_id="tenant-a", case_id=first.case_id, version_number=1)
        is None
    )
    assert await repo.duplicate_owner(tenant_id="tenant-a", duplicate_key="a" * 64) is None


@pytest.mark.asyncio
async def test_atomic_duplicate_claim_persists_loser_case_and_is_tenant_scoped(
    db: AsyncSession,
) -> None:
    repo = SqlAlchemyInvoiceCaseRepository(db)
    first = await _create(repo, key="a" * 64)
    duplicate = await _create(repo, key="a" * 64)
    other_tenant = await _create(repo, key="a" * 64, tenant="tenant-b")
    assert duplicate.case_id != first.case_id
    assert duplicate.duplicate_of == first.case_id and duplicate.status == "duplicate"
    assert other_tenant.duplicate_of is None
    assert await repo.duplicate_owner(tenant_id="tenant-a", duplicate_key="a" * 64) == first.case_id
    assert (
        await repo.duplicate_owner(tenant_id="tenant-b", duplicate_key="a" * 64)
        == other_tenant.case_id
    )
    await db.commit()


@pytest.mark.asyncio
async def test_revisions_reuse_own_claim_and_retain_old_claims(db: AsyncSession) -> None:
    repo = SqlAlchemyInvoiceCaseRepository(db)
    first = await _create(repo, key="a" * 64)
    second = await repo.append(
        case_id=first.case_id,
        package=_package(amount="200.00"),
        assessment=_assessment(),
        duplicate_key="a" * 64,
        expected_version=1,
        actor=_actor(),
    )
    assert second.duplicate_of is None
    third = await repo.append(
        case_id=first.case_id,
        package=_package(amount="300.00"),
        assessment=_assessment(),
        duplicate_key="b" * 64,
        expected_version=2,
        actor=_actor(),
    )
    assert third.duplicate_of is None
    assert await repo.duplicate_owner(tenant_id="tenant-a", duplicate_key="a" * 64) == first.case_id
    assert await repo.duplicate_owner(tenant_id="tenant-a", duplicate_key="b" * 64) == first.case_id
    versions = await repo.list_versions(tenant_id="tenant-a", case_id=first.case_id)
    assert [v.version_number for v in versions] == [3, 2, 1]
    assert versions[2].package.invoice.fields.total == "100.00"


@pytest.mark.asyncio
async def test_all_case_operations_are_tenant_scoped(db: AsyncSession) -> None:
    repo = SqlAlchemyInvoiceCaseRepository(db)
    first = await _create(repo)
    assert (
        await repo.get_version(tenant_id="tenant-b", case_id=first.case_id, version_number=1)
        is None
    )
    assert await repo.list_versions(tenant_id="tenant-b", case_id=first.case_id) == ()
    assert await repo.list_latest(tenant_id="tenant-b") == ()
    with pytest.raises(AgreementMasterError):
        await repo.append(
            case_id=first.case_id,
            package=_package(),
            assessment=_assessment(),
            duplicate_key=None,
            expected_version=1,
            actor=_actor(tenant="tenant-b"),
        )
    with pytest.raises(AgreementMasterError):
        await repo.decide(
            case_id=first.case_id,
            expected_version=1,
            decision=APDecision(action="reject", reason="Not matched"),
            actor=_actor(tenant="tenant-b", approve=True),
        )


@pytest.mark.asyncio
async def test_stale_version_and_repeat_decision_conflict(db: AsyncSession) -> None:
    repo = SqlAlchemyInvoiceCaseRepository(db)
    first = await _create(repo)
    await repo.append(
        case_id=first.case_id,
        package=_package(),
        assessment=_assessment(),
        duplicate_key=None,
        expected_version=1,
        actor=_actor(),
    )
    for operation in (
        repo.append(
            case_id=first.case_id,
            package=_package(),
            assessment=_assessment(),
            duplicate_key=None,
            expected_version=1,
            actor=_actor(),
        ),
        repo.lock_for_decision(
            case_id=first.case_id, expected_version=1, actor=_actor(approve=True), agreement_id=None
        ),
    ):
        with pytest.raises(AgreementMasterError) as caught:
            await operation
        assert caught.value.code == "conflict"
    await repo.decide(
        case_id=first.case_id,
        expected_version=2,
        decision=APDecision(action="reject", reason="Reviewed"),
        actor=_actor(approve=True),
    )
    for operation in (
        repo.decide(
            case_id=first.case_id,
            expected_version=2,
            decision=APDecision(action="approve", reason="Reviewed"),
            actor=_actor(approve=True),
        ),
        repo.lock_for_decision(
            case_id=first.case_id, expected_version=2, actor=_actor(approve=True), agreement_id=None
        ),
    ):
        with pytest.raises(AgreementMasterError) as caught:
            await operation
        assert caught.value.code == "conflict"
    await db.commit()


@pytest.mark.asyncio
async def test_duplicate_cannot_be_approved_even_through_adapter(db: AsyncSession) -> None:
    repo = SqlAlchemyInvoiceCaseRepository(db)
    await _create(repo, key="a" * 64)
    duplicate = await _create(repo, key="a" * 64)
    with pytest.raises(AgreementMasterError) as caught:
        await repo.decide(
            case_id=duplicate.case_id,
            expected_version=1,
            decision=APDecision(action="approve", reason="Reviewed"),
            actor=_actor(approve=True),
        )
    assert caught.value.code == "conflict"
    rejected = await repo.decide(
        case_id=duplicate.case_id,
        expected_version=1,
        decision=APDecision(action="reject", reason="Duplicate"),
        actor=_actor(approve=True),
    )
    assert rejected.status == "rejected"


@pytest.mark.asyncio
async def test_identity_cannot_change_in_revision(db: AsyncSession) -> None:
    repo = SqlAlchemyInvoiceCaseRepository(db)
    first = await _create(repo)
    with pytest.raises(AgreementMasterError) as caught:
        await repo.append(
            case_id=first.case_id,
            package=_package(vendor_id="another-vendor"),
            assessment=_assessment(),
            duplicate_key=None,
            expected_version=1,
            actor=_actor(),
        )
    assert caught.value.code == "conflict"
    assert len(await repo.list_versions(tenant_id="tenant-a", case_id=first.case_id)) == 1


@pytest.mark.asyncio
async def test_latest_queue_has_latest_version_and_tenant_pagination(db: AsyncSession) -> None:
    repo = SqlAlchemyInvoiceCaseRepository(db)
    first = await _create(repo)
    await repo.append(
        case_id=first.case_id,
        package=_package(),
        assessment=_assessment(),
        duplicate_key=None,
        expected_version=1,
        actor=_actor(),
    )
    second = await _create(repo)
    latest = await repo.list_latest(tenant_id="tenant-a")
    assert [(v.case_id, v.version_number) for v in latest] == [
        (second.case_id, 1),
        (first.case_id, 2),
    ]
    assert (await repo.list_latest(tenant_id="tenant-a", limit=1, offset=1))[
        0
    ].case_id == first.case_id


@pytest.mark.asyncio
async def test_snapshots_decisions_claims_and_header_identity_are_immutable(
    db: AsyncSession,
) -> None:
    repo = SqlAlchemyInvoiceCaseRepository(db)
    first = await _create(repo, key="a" * 64)
    await repo.decide(
        case_id=first.case_id,
        expected_version=1,
        decision=APDecision(action="approve", reason="Reviewed"),
        actor=_actor(approve=True),
    )
    await db.commit()
    for model, field, value in (
        (InvoiceCaseVersionRow, "package", {"overwritten": True}),
        (InvoiceCaseDecision, "decision", {"action": "reject"}),
        (InvoiceDuplicateClaim, "duplicate_key", "c" * 64),
        (InvoiceCase, "vendor_id", "other"),
    ):
        row = (await db.execute(select(model))).scalar_one()
        setattr(row, field, value)
        with pytest.raises(ValueError, match="immutable"):
            await db.flush()
        await db.rollback()


@pytest.mark.asyncio
async def test_composite_foreign_keys_reject_cross_tenant_claim_and_version(
    db: AsyncSession,
) -> None:
    repo = SqlAlchemyInvoiceCaseRepository(db)
    first = await _create(repo)
    await db.commit()
    for row in (
        InvoiceDuplicateClaim(tenant_id="tenant-b", duplicate_key="a" * 64, case_id=first.case_id),
        InvoiceCaseVersionRow(
            tenant_id="tenant-b",
            case_id=first.case_id,
            version_number=2,
            package=_package().model_dump(mode="json"),
            assessment=_assessment().model_dump(mode="json"),
            created_by="author",
        ),
    ):
        with pytest.raises(IntegrityError):
            async with db.begin_nested():
                db.add(row)
                await db.flush()


@pytest.mark.asyncio
async def test_composite_foreign_keys_reject_cross_tenant_decision_and_duplicate_link(
    db: AsyncSession,
) -> None:
    repo = SqlAlchemyInvoiceCaseRepository(db)
    first = await _create(repo)
    other_tenant = await _create(repo, tenant="tenant-b")
    await db.commit()
    for row in (
        InvoiceCaseDecision(
            tenant_id="tenant-b",
            case_id=first.case_id,
            version_number=1,
            decision=APDecision(action="reject", reason="Review").model_dump(mode="json"),
            decided_by="author",
        ),
        InvoiceCaseVersionRow(
            tenant_id="tenant-a",
            case_id=first.case_id,
            version_number=2,
            package=_package().model_dump(mode="json"),
            assessment=_assessment().model_dump(mode="json"),
            duplicate_of=other_tenant.case_id,
            created_by="author",
        ),
    ):
        with pytest.raises(IntegrityError):
            async with db.begin_nested():
                db.add(row)
                await db.flush()


@pytest.mark.asyncio
async def test_returned_and_input_collections_cannot_mutate_stored_snapshots(
    db: AsyncSession,
) -> None:
    repo = SqlAlchemyInvoiceCaseRepository(db)
    package = _package()
    first = await repo.create(
        package=package, assessment=_assessment(), duplicate_key=None, actor=_actor()
    )
    package.invoice.fields.extensions["batch"].append("source changed")
    first.package.invoice.fields.extensions["batch"].append("returned changed")
    await db.commit()
    found = await repo.get_version(tenant_id="tenant-a", case_id=first.case_id, version_number=1)
    assert found is not None and found.package.invoice.fields.extensions == {"batch": ["one"]}
