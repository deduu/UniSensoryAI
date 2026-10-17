"""UI agreement queues retain tenant, version, and deterministic page boundaries."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.agreement_version import AgreementVersion as AgreementVersionRow
from src.paper.contracts import AgreementIdentity
from src.services.agreement_repository import SqlAlchemyAgreementRepository
from tests.integration.test_paper_agreement_master import _actor, _decision, _draft
from tests.integration.test_paper_agreement_master import db as agreement_db

db = agreement_db


@pytest.mark.asyncio
async def test_latest_agreement_queue_paginates_without_tenant_or_version_leaks(
    db: AsyncSession,
) -> None:
    repository = SqlAlchemyAgreementRepository(db)
    first = await repository.create(
        identity=AgreementIdentity(
            vendor_id="vendor-1", store_id="store-1", contract_number="RA-1"
        ),
        draft=_draft(),
        actor=_actor(),
    )
    await repository.approve(
        agreement_id=first.agreement_id,
        version_number=1,
        decision=_decision(),
        actor=_actor(approve=True),
    )
    latest = await repository.append(
        agreement_id=first.agreement_id,
        expected_version=1,
        draft=_draft(amount="2000000"),
        actor=_actor(),
    )
    second = await repository.create(
        identity=AgreementIdentity(
            vendor_id="vendor-2", store_id="store-2", contract_number="RA-2"
        ),
        draft=_draft(),
        actor=_actor(),
    )
    private = await repository.create(
        identity=first.identity, draft=_draft(), actor=_actor(tenant_id="tenant-b")
    )
    # Make the ordering tie deliberate: pagination must have a stable identifier tiebreaker.
    await db.execute(
        update(AgreementVersionRow).values(created_at=datetime(2026, 6, 1, tzinfo=timezone.utc))
    )
    await db.commit()
    results = await repository.list_latest(tenant_id="tenant-a")
    expected_ids = sorted((first.agreement_id, second.agreement_id), reverse=True)
    assert [item.agreement_id for item in results] == expected_ids
    assert all(item.tenant_id == "tenant-a" for item in results)
    current_first = next(item for item in results if item.agreement_id == first.agreement_id)
    assert current_first.version_number == latest.version_number == 2
    assert current_first.approval is None
    assert current_first.draft.terms.fixed_rent == "2000000"
    for offset, identifier in enumerate(expected_ids):
        page = await repository.list_latest(tenant_id="tenant-a", limit=1, offset=offset)
        assert len(page) == 1
        assert page[0].agreement_id == identifier
    assert await repository.list_latest(tenant_id="tenant-a", limit=1, offset=2) == ()
    assert [item.agreement_id for item in await repository.list_latest(tenant_id="tenant-b")] == [
        private.agreement_id
    ]
