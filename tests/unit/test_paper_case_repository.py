"""Mocked checks for tenant guards and host-owned case transactions."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from src.paper.contracts import AgreementActor, AgreementIdentity
from src.paper.errors import AgreementMasterError
from src.paper.reconciliation.contracts import (
    APDecision,
    InvoicePackage,
    ReconciliationAssessment,
    RentInvoiceDocument,
)
from src.paper.schemas import RentInvoiceSchema
from src.services.invoice_case_repository import SqlAlchemyInvoiceCaseRepository


def _session() -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()
    session.begin_nested = MagicMock()
    session.begin_nested.return_value.__aenter__ = AsyncMock()
    session.begin_nested.return_value.__aexit__ = AsyncMock(return_value=False)
    return session


def _package() -> InvoicePackage:
    return InvoicePackage(
        identity=AgreementIdentity(
            vendor_id="vendor-1", store_id="store-1", contract_number="RA-1"
        ),
        invoice=RentInvoiceDocument(
            source_document_id="source-1", fields=RentInvoiceSchema(invoice_number="INV-1")
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


@pytest.mark.asyncio
async def test_unauthorized_decision_has_no_io() -> None:
    db = _session()
    with pytest.raises(AgreementMasterError) as caught:
        await SqlAlchemyInvoiceCaseRepository(db).decide(
            case_id="case-1",
            expected_version=1,
            decision=APDecision(action="approve", reason="Reviewed"),
            actor=AgreementActor(tenant_id="tenant-1", user_id="member"),
        )
    assert caught.value.code == "forbidden"
    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_stale_case_lock_uses_tenant_and_revision_compare_and_swap() -> None:
    db = _session()
    db.execute.return_value = MagicMock(rowcount=0)
    with pytest.raises(AgreementMasterError) as caught:
        await SqlAlchemyInvoiceCaseRepository(db).lock_for_decision(
            case_id="case-1",
            expected_version=2,
            actor=AgreementActor(tenant_id="tenant-1", user_id="ap", can_approve=True),
            agreement_id="agreement-1",
        )
    assert caught.value.code == "conflict"
    statement = db.execute.await_args.args[0]
    params = statement.compile().params
    assert params["tenant_id_1"] == "tenant-1"
    assert params["latest_version_1"] == 2
    assert "paperinvoicecases" in str(statement.compile())
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_reference_lock_scopes_agreement_and_holds_host_transaction() -> None:
    db = _session()
    current = MagicMock()
    current.first.return_value = (MagicMock(), MagicMock(), None)
    db.execute.side_effect = [MagicMock(rowcount=1), current, MagicMock(rowcount=1)]
    await SqlAlchemyInvoiceCaseRepository(db).lock_for_decision(
        case_id="case-1",
        expected_version=1,
        actor=AgreementActor(tenant_id="tenant-1", user_id="ap", can_approve=True),
        agreement_id="agreement-1",
    )
    statement = db.execute.await_args_list[-1].args[0]
    assert "UPDATE paperagreements" in str(statement.compile())
    assert "tenant-1" in statement.compile().params.values()
    assert "agreement-1" in statement.compile().params.values()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_integrity_error_is_sanitized_and_does_not_commit() -> None:
    db = _session()
    db.flush.side_effect = IntegrityError("sensitive SQL", {}, Exception("sensitive"))
    with pytest.raises(AgreementMasterError) as caught:
        await SqlAlchemyInvoiceCaseRepository(db).create(
            package=_package(),
            assessment=_assessment(),
            duplicate_key=None,
            actor=AgreementActor(tenant_id="tenant-1", user_id="author"),
        )
    assert caught.value.code == "conflict"
    assert "sensitive" not in str(caught.value)
    assert caught.value.__cause__ is None
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_duplicate_claim_unique_race_persists_distinct_loser_case() -> None:
    db = _session()
    unclaimed = MagicMock()
    unclaimed.scalar_one_or_none.return_value = None
    claimed = MagicMock()
    claimed.scalar_one_or_none.return_value = "winning-case"
    db.execute.side_effect = [unclaimed, claimed]
    db.flush.side_effect = [None, IntegrityError("private SQL", {}, Exception("private")), None]
    created = await SqlAlchemyInvoiceCaseRepository(db).create(
        package=_package(),
        assessment=_assessment(),
        duplicate_key="a" * 64,
        actor=AgreementActor(tenant_id="tenant-1", user_id="author"),
    )
    assert created.case_id != "winning-case"
    assert created.duplicate_of == "winning-case"
    assert created.status == "duplicate"
    assert db.flush.await_count == 3
    assert db.begin_nested.call_count == 2
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_duplicate_claim_failure_without_owner_is_sanitized_conflict() -> None:
    db = _session()
    missing = MagicMock()
    missing.scalar_one_or_none.return_value = None
    db.execute.return_value = missing
    db.flush.side_effect = [None, IntegrityError("private SQL", {}, Exception("private"))]
    with pytest.raises(AgreementMasterError) as caught:
        await SqlAlchemyInvoiceCaseRepository(db).create(
            package=_package(),
            assessment=_assessment(),
            duplicate_key="a" * 64,
            actor=AgreementActor(tenant_id="tenant-1", user_id="author"),
        )
    assert caught.value.code == "conflict"
    assert "private" not in str(caught.value)
    assert caught.value.__cause__ is None
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("tenant_id,version", [("", 1), ("tenant-1", 0), ("tenant-1", True)])
async def test_primitive_validation_precedes_io(tenant_id: str, version: int) -> None:
    db = _session()
    with pytest.raises(AgreementMasterError):
        await SqlAlchemyInvoiceCaseRepository(db).get_version(
            tenant_id=tenant_id, case_id="case-1", version_number=version
        )
    db.execute.assert_not_awaited()
