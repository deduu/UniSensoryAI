"""Tenant guards and transaction behavior of the agreement repository."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

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


def _draft() -> AgreementDraft:
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
            fixed_rent="1000000.00",
        ),
        effective_from=date(2026, 1, 1),
        effective_to=date(2026, 12, 31),
        source_document_ids=("source-1",),
        change_reason="Initial terms",
    )


def _session() -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()
    session.begin_nested = MagicMock()
    session.begin_nested.return_value.__aenter__ = AsyncMock()
    session.begin_nested.return_value.__aexit__ = AsyncMock(return_value=False)
    return session


@pytest.mark.asyncio
async def test_repository_rejects_unauthorized_approval_without_io() -> None:
    session = _session()
    repository = SqlAlchemyAgreementRepository(session)
    with pytest.raises(AgreementMasterError) as caught:
        await repository.approve(
            agreement_id="agreement-1",
            version_number=1,
            decision=ApprovalDecision(
                classification="psak73",
                rule_set_id="accounting",
                rule_set_version="1",
                reason="Reviewed",
            ),
            actor=AgreementActor(tenant_id="tenant-1", user_id="member"),
        )
    assert caught.value.code == "forbidden"
    session.execute.assert_not_awaited()
    session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_integrity_error_is_sanitized_inside_savepoint() -> None:
    session = _session()
    session.flush.side_effect = IntegrityError("sensitive SQL", {}, Exception("sensitive"))
    repository = SqlAlchemyAgreementRepository(session)
    with pytest.raises(AgreementMasterError) as caught:
        await repository.create(
            identity=AgreementIdentity(
                vendor_id="vendor-1", store_id="store-1", contract_number="RA-1"
            ),
            draft=_draft(),
            actor=AgreementActor(tenant_id="tenant-1", user_id="author"),
        )
    assert caught.value.code == "conflict"
    assert "sensitive" not in str(caught.value)
    assert caught.value.__cause__ is None
    session.begin_nested.assert_called_once()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_stale_append_performs_tenant_scoped_compare_and_swap() -> None:
    session = _session()
    session.execute.return_value = MagicMock(rowcount=0)
    repository = SqlAlchemyAgreementRepository(session)
    with pytest.raises(AgreementMasterError) as caught:
        await repository.append(
            agreement_id="agreement-1",
            draft=_draft(),
            expected_version=2,
            actor=AgreementActor(tenant_id="tenant-1", user_id="author"),
        )
    assert caught.value.code == "conflict"
    statement = session.execute.await_args.args[0]
    assert statement.compile().params["tenant_id_1"] == "tenant-1"
    assert statement.compile().params["latest_version_1"] == 2
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_approved_lookup_filters_tenant_identity_date_and_approval() -> None:
    session = _session()
    result = MagicMock()
    result.first.return_value = None
    session.execute.return_value = result
    repository = SqlAlchemyAgreementRepository(session)
    found = await repository.find_approved(
        tenant_id="tenant-1",
        lookup=AgreementLookup(
            identity=AgreementIdentity(
                vendor_id="vendor-1", store_id="store-1", contract_number="RA-1"
            ),
            as_of=date(2026, 6, 1),
        ),
    )
    assert found is None
    statement = session.execute.await_args.args[0]
    sql = str(statement.compile())
    params = statement.compile().params
    assert "paperagreementapprovals" in sql
    assert "DESC" in sql
    assert "tenant-1" in params.values()
    assert "vendor-1" in params.values()
    assert "store-1" in params.values()
    assert "RA-1" in params.values()
    assert date(2026, 6, 1) in params.values()


@pytest.mark.asyncio
@pytest.mark.parametrize("tenant_id,version", [("", 1), ("tenant-1", 0), ("tenant-1", True)])
async def test_repository_validates_primitive_inputs_before_io(
    tenant_id: str, version: int
) -> None:
    session = _session()
    with pytest.raises(AgreementMasterError) as caught:
        await SqlAlchemyAgreementRepository(session).get_version(
            tenant_id=tenant_id, agreement_id="agreement-1", version_number=version
        )
    assert caught.value.code == "invalid_agreement"
    session.execute.assert_not_awaited()
