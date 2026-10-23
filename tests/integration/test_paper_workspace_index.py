"""Read-only workspace indexes retain exact relations, tenant and page boundaries."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.ingestion import IngestionJob, IngestionStatus
from src.db.models.invoice_case import InvoiceCase
from src.db.models.invoice_case_decision import InvoiceCaseDecision
from src.db.models.invoice_case_version import InvoiceCaseVersion
from src.paper.workspace.contracts import WorkspaceQuery
from src.services.agreement_repository import SqlAlchemyAgreementRepository
from src.services.paper_workspace_index import PaperWorkspaceIndexService
from tests.integration.test_paper_agreement_master import _actor, _decision, _draft, _identity
from tests.integration.test_paper_agreement_master import db as agreement_db

db = agreement_db
NOW = datetime(2026, 10, 18, tzinfo=timezone.utc)


async def _case(
    db: AsyncSession,
    identifier: str,
    *,
    tenant: str = "tenant-a",
    source: str = "invoice-source",
    agreement: str | None = None,
    confirmed: bool = True,
    outcome: str = "incomplete",
    number: str = "INV-1",
    version: int = 1,
) -> None:
    if version == 1:
        db.add(
            InvoiceCase(
                id=identifier,
                tenant_id=tenant,
                vendor_id="vendor-1",
                store_id="store-1",
                contract_number="RA-1",
                latest_version=version,
                created_at=NOW,
            )
        )
        await db.flush()
    association = (
        {"agreement_id": agreement, "version_number": 1, "reason": "Reviewed"}
        if agreement
        else None
    )
    if association is not None and confirmed:
        association.update(
            confirmed_by="reviewer",
            confirmed_at=NOW.isoformat(),
            invoice_fingerprint="a" * 64,
            signals=[],
            policy_id="association",
            policy_version="1",
        )
    db.add(
        InvoiceCaseVersion(
            tenant_id=tenant,
            case_id=identifier,
            version_number=version,
            package={
                "identity": _identity().model_dump(),
                "invoice": {
                    "source_document_id": source,
                    "fields": {
                        "invoice_number": number,
                        "vendor_name": "Landlord",
                        "location": "Tanjung Selor",
                    },
                },
                "association": association,
            },
            assessment={
                "outcome": outcome,
                "findings": [
                    {"severity": "blocking", "code": "missing_period"},
                    {"severity": "review", "code": "source_discrepancy"},
                ],
            },
            created_by="reviewer",
            created_at=NOW,
        )
    )
    await db.flush()


@pytest.mark.asyncio
async def test_cases_filter_before_paging_and_never_infer_confirmation(db: AsyncSession) -> None:
    master = SqlAlchemyAgreementRepository(db)
    agreement = await master.create(identity=_identity(), draft=_draft(), actor=_actor())
    await _case(db, "case-z", agreement=agreement.agreement_id, number="INVOICE-z")
    await _case(db, "case-a", agreement=agreement.agreement_id, number="INVOICE-a")
    await _case(db, "case-legacy", number="LEGACY")
    await _case(db, "case-unconfirmed", agreement=agreement.agreement_id, confirmed=False)
    await _case(db, "private", tenant="tenant-b", agreement=agreement.agreement_id)
    service = PaperWorkspaceIndexService(db)
    page = await service.cases(
        "tenant-a",
        WorkspaceQuery(q="INVOICE", agreement_id=agreement.agreement_id, limit=1, offset=1),
    )
    assert page.total == 2
    assert len(page.items) == 1
    assert page.items[0].case_id == "case-a"
    assert page.items[0].association.kind == "confirmed"
    assert page.items[0].blocking_count == 1
    assert page.items[0].review_count == 1
    legacy = await service.cases(
        "tenant-a",
        WorkspaceQuery(agreement_id=agreement.agreement_id, association_kind="legacy_identity"),
    )
    assert [item.case_id for item in legacy.items] == ["case-legacy"]
    assert legacy.items[0].association.kind == "legacy_identity"


@pytest.mark.asyncio
async def test_contract_latest_draft_keeps_prior_approval_and_confirmed_invoice_count(
    db: AsyncSession,
) -> None:
    repository = SqlAlchemyAgreementRepository(db)
    agreement = await repository.create(identity=_identity(), draft=_draft(), actor=_actor())
    await repository.approve(
        agreement_id=agreement.agreement_id,
        version_number=1,
        decision=_decision(),
        actor=_actor(approve=True),
    )
    await repository.append(
        agreement_id=agreement.agreement_id, expected_version=1, draft=_draft(), actor=_actor()
    )
    await _case(db, "linked", agreement=agreement.agreement_id)
    await _case(db, "legacy")
    await _case(db, "other-tenant", tenant="tenant-b", agreement=agreement.agreement_id)
    page = await PaperWorkspaceIndexService(db).contracts(
        "tenant-a", WorkspaceQuery(q="Landlord", status="draft")
    )
    assert page.total == 1
    item = page.items[0]
    assert item.version_number == 2
    assert item.status == "draft"
    assert item.approved_version_number == 1
    assert item.linked_case_count == 1
    assert item.legacy_case_count == 1


@pytest.mark.asyncio
async def test_documents_join_exact_sources_and_preserve_historical_link(db: AsyncSession) -> None:
    repository = SqlAlchemyAgreementRepository(db)
    agreement = await repository.create(identity=_identity(), draft=_draft(), actor=_actor())
    revised = _draft().model_copy(update={"source_document_ids": ("different-source",)})
    await repository.append(
        agreement_id=agreement.agreement_id, expected_version=1, draft=revised, actor=_actor()
    )
    db.add_all(
        [
            IngestionJob(
                id="job-contract",
                tenant_id="tenant-a",
                file_path="private.pdf",
                status=IngestionStatus.COMPLETED,
                created_at=NOW,
                updated_at=NOW,
                meta={
                    "workflow": "paper_extraction",
                    "original_filename": "Contract.pdf",
                    "schema_name": "rent_agreement",
                    "document_id": "source-1",
                },
            ),
            IngestionJob(
                id="job-unlinked",
                tenant_id="tenant-a",
                file_path="private.pdf",
                status=IngestionStatus.COMPLETED,
                created_at=NOW,
                updated_at=NOW,
                meta={
                    "workflow": "paper_extraction",
                    "original_filename": "Contract.pdf",
                    "schema_name": "rent_agreement",
                    "document_id": "not-the-same",
                },
            ),
            IngestionJob(
                id="private-job",
                tenant_id="tenant-b",
                file_path="private.pdf",
                status=IngestionStatus.COMPLETED,
                created_at=NOW,
                updated_at=NOW,
                meta={
                    "workflow": "paper_extraction",
                    "original_filename": "Contract.pdf",
                    "schema_name": "rent_agreement",
                    "document_id": "source-1",
                },
            ),
        ]
    )
    await db.flush()
    page = await PaperWorkspaceIndexService(db).documents("tenant-a", WorkspaceQuery(q="Contract"))
    assert page.total == 2
    linked = next(item for item in page.items if item.job_id == "job-contract")
    assert linked.workflow_links[0].id == agreement.agreement_id
    assert linked.workflow_links[0].version_number == 1
    assert linked.workflow_links[0].is_latest is False
    assert linked.workflow_status == "agreement_draft"
    assert "private.pdf" not in linked.model_dump_json()
    unlinked = next(item for item in page.items if item.job_id == "job-unlinked")
    assert unlinked.workflow_links == ()
    assert unlinked.next_action == "review_agreement"
    assert len((await db.execute(select(IngestionJob))).scalars().all()) == 3
    filtered = await PaperWorkspaceIndexService(db).documents(
        "tenant-a", WorkspaceQuery(workflow_status="agreement_draft", limit=1)
    )
    assert filtered.total == 1
    assert filtered.items[0].job_id == "job-contract"
    ready = await PaperWorkspaceIndexService(db).documents(
        "tenant-a", WorkspaceQuery(workflow_status="ready_for_review")
    )
    assert ready.total == 1
    assert ready.items[0].job_id == "job-unlinked"


@pytest.mark.asyncio
async def test_exact_document_lookup_includes_archived_source_but_not_other_tenant(
    db: AsyncSession,
) -> None:
    db.add(
        IngestionJob(
            id="archived-job",
            tenant_id="tenant-a",
            file_path="private.pdf",
            status=IngestionStatus.COMPLETED,
            created_at=NOW,
            updated_at=NOW,
            meta={
                "workflow": "paper_extraction",
                "original_filename": "Archived.pdf",
                "schema_name": "rent_invoice",
                "paper_archive": {"archived": True},
            },
        )
    )
    await db.flush()
    service = PaperWorkspaceIndexService(db)
    assert (await service.documents("tenant-a", WorkspaceQuery())).total == 0
    exact = await service.documents("tenant-a", WorkspaceQuery(job_id="archived-job", limit=1))
    assert exact.total == 1
    assert exact.items[0].archived is True
    assert exact.items[0].workflow_links_resolved is False
    assert (await service.documents("tenant-b", WorkspaceQuery(job_id="archived-job"))).total == 0


@pytest.mark.asyncio
async def test_latest_case_status_search_does_not_reopen_old_revisions(db: AsyncSession) -> None:
    await _case(db, "revised", number="OLD-NUMBER", outcome="mismatched")
    await _case(db, "revised", number="NEW-NUMBER", outcome="matched", version=2)
    await db.execute(
        update(InvoiceCase).where(InvoiceCase.id == "revised").values(latest_version=2)
    )
    db.add(
        InvoiceCaseDecision(
            tenant_id="tenant-a",
            case_id="revised",
            version_number=2,
            decision={"action": "approve", "reason": "Reviewed"},
            decided_by="reviewer",
            decided_at=NOW,
        )
    )
    await db.flush()
    service = PaperWorkspaceIndexService(db)
    assert (await service.cases("tenant-a", WorkspaceQuery(q="OLD-NUMBER"))).total == 0
    assert (await service.cases("tenant-a", WorkspaceQuery(status="mismatched"))).total == 0
    page = await service.cases("tenant-a", WorkspaceQuery(status="approved"))
    assert page.total == 1
    assert page.items[0].version_number == 2
    assert page.items[0].next_action == "view_case"


@pytest.mark.asyncio
async def test_document_links_are_bounded_and_advertise_total(db: AsyncSession) -> None:
    for number in range(23):
        await _case(db, f"case-{number:02}", source="shared-invoice")
    db.add(
        IngestionJob(
            id="shared-job",
            tenant_id="tenant-a",
            file_path="private.pdf",
            status=IngestionStatus.COMPLETED,
            created_at=NOW,
            updated_at=NOW,
            meta={
                "workflow": "paper_extraction",
                "original_filename": "Invoice.pdf",
                "schema_name": "rent_invoice",
                "document_id": "shared-invoice",
            },
        )
    )
    await db.flush()
    service = PaperWorkspaceIndexService(db)
    page = await service.documents(
        "tenant-a", WorkspaceQuery(workflow_status="invoice_case", limit=1)
    )
    assert page.total == 1
    item = page.items[0]
    assert len(item.workflow_links) == 20
    assert item.workflow_links_total == 23
    assert item.next_action == "open_case"
    assert item.workflow_links[0].id == "case-22"


@pytest.mark.asyncio
async def test_search_treats_sql_wildcards_as_literal_text(db: AsyncSession) -> None:
    await _case(db, "literal", number="INV_100%")
    await _case(db, "similar", number="INVA1000")
    result = await PaperWorkspaceIndexService(db).cases("tenant-a", WorkspaceQuery(q="_100%"))
    assert result.total == 1
    assert result.items[0].case_id == "literal"
