"""Bounded asynchronous read model for PAPER case and document navigation."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from typing import Any, Literal, TypeVar, cast

from pydantic import TypeAdapter
from sqlalchemy import and_, case, func, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.agreement import Agreement
from src.db.models.agreement_approval import AgreementApproval
from src.db.models.agreement_version import AgreementVersion
from src.db.models.ingestion import IngestionJob
from src.db.models.invoice_case import InvoiceCase
from src.db.models.invoice_case_decision import InvoiceCaseDecision
from src.db.models.invoice_case_version import InvoiceCaseVersion
from src.paper.contracts import AgreementIdentity
from src.paper.contracts._base import Identifier
from src.paper.errors import AgreementMasterError
from src.paper.workspace.contracts import (
    WorkspaceAssociation,
    WorkspaceCase,
    WorkspaceContract,
    WorkspaceDocument,
    WorkspaceLink,
    WorkspacePage,
    WorkspaceQuery,
)

_Tenant = TypeAdapter(Identifier)
_Result = TypeVar("_Result")
_LINK_LIMIT = 20
_CaseAction = Literal["view_case", "review_duplicate", "review_and_decide", "resolve_discrepancies"]
_DocumentState = Literal[
    "processing",
    "extraction_failed",
    "ready_for_review",
    "agreement_draft",
    "agreement_approved",
    "invoice_case",
]
_DocumentAction = Literal[
    "wait_for_extraction",
    "retry_extraction",
    "review_agreement",
    "review_invoice",
    "open_agreement",
    "open_case",
]


def _case_status() -> Any:
    return case(
        (InvoiceCaseDecision.decision["action"].as_string() == "approve", "approved"),
        (InvoiceCaseDecision.decision["action"].as_string() == "reject", "rejected"),
        (InvoiceCaseVersion.duplicate_of.is_not(None), "duplicate"),
        else_=InvoiceCaseVersion.assessment["outcome"].as_string(),
    )


def _confirmed() -> Any:
    association = InvoiceCaseVersion.package["association"]
    return and_(
        association["agreement_id"].as_string().is_not(None),
        association["confirmed_by"].as_string().is_not(None),
        association["confirmed_at"].as_string().is_not(None),
        association["invoice_fingerprint"].as_string().is_not(None),
    )


def _case_query(tenant_id: str) -> Any:
    return (
        select(InvoiceCase, InvoiceCaseVersion, _case_status().label("status"))
        .join(
            InvoiceCaseVersion,
            and_(
                InvoiceCase.tenant_id == InvoiceCaseVersion.tenant_id,
                InvoiceCase.id == InvoiceCaseVersion.case_id,
                InvoiceCase.latest_version == InvoiceCaseVersion.version_number,
            ),
        )
        .outerjoin(
            InvoiceCaseDecision,
            and_(
                InvoiceCaseVersion.tenant_id == InvoiceCaseDecision.tenant_id,
                InvoiceCaseVersion.case_id == InvoiceCaseDecision.case_id,
                InvoiceCaseVersion.version_number == InvoiceCaseDecision.version_number,
            ),
        )
        .where(InvoiceCase.tenant_id == tenant_id)
    )


def _search(query: Any, text: str, columns: tuple[Any, ...]) -> Any:
    text = text.strip()
    return (
        query.where(or_(*(column.icontains(text, autoescape=True) for column in columns)))
        if text
        else query
    )


class PaperWorkspaceIndexService:
    """Read tenant-owned navigation summaries without loading models or writing history.

    Args:
        db: Host async session; this service never commits or mutates it.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def _bounded(self, operation: Awaitable[_Result]) -> _Result:
        try:
            return await asyncio.wait_for(operation, timeout=15)
        except asyncio.TimeoutError:
            raise AgreementMasterError(
                "timeout", "Workspace navigation exceeded its storage deadline."
            ) from None

    async def _page(self, query: Any, params: WorkspaceQuery) -> tuple[list[Any], int]:
        count = await self._db.scalar(
            select(func.count()).select_from(query.order_by(None).subquery())
        )
        result = await self._db.execute(query.limit(params.limit).offset(params.offset))
        return list(result.all()), int(count or 0)

    async def cases(self, tenant_id: str, params: WorkspaceQuery) -> WorkspacePage[WorkspaceCase]:
        """Search latest cases before paging, optionally by an explicit contract relation."""
        return await self._bounded(
            self._cases(_Tenant.validate_python(tenant_id), WorkspaceQuery.model_validate(params))
        )

    async def _cases(self, tenant_id: str, params: WorkspaceQuery) -> WorkspacePage[WorkspaceCase]:
        query = _case_query(tenant_id)
        fields = InvoiceCaseVersion.package["invoice"]["fields"]
        query = _search(
            query,
            params.q,
            (
                fields["invoice_number"].as_string(),
                fields["vendor_name"].as_string(),
                fields["location"].as_string(),
                InvoiceCase.contract_number,
                InvoiceCase.vendor_id,
                InvoiceCase.store_id,
            ),
        )
        if params.status:
            query = query.where(_case_status() == params.status)
        linked_identity = None
        if params.agreement_id:
            agreement = await self._db.scalar(
                select(Agreement).where(
                    Agreement.tenant_id == tenant_id, Agreement.id == params.agreement_id
                )
            )
            if agreement is None:
                return WorkspacePage(items=(), total=0, limit=params.limit, offset=params.offset)
            if params.association_kind == "legacy_identity":
                linked_identity = agreement
                query = query.where(
                    InvoiceCaseVersion.package["association"]["agreement_id"].as_string().is_(None),
                    InvoiceCase.vendor_id == agreement.vendor_id,
                    InvoiceCase.store_id == agreement.store_id,
                    InvoiceCase.contract_number == agreement.contract_number,
                )
            else:
                query = query.where(
                    _confirmed(),
                    InvoiceCaseVersion.package["association"]["agreement_id"].as_string()
                    == agreement.id,
                )
        rows, total = await self._page(
            query.order_by(InvoiceCaseVersion.created_at.desc(), InvoiceCase.id.desc()), params
        )
        items = []
        for header, snapshot, status in rows:
            package = snapshot.package
            data = package.get("invoice", {}).get("fields", {})
            raw_association = package.get("association") or {}
            association = None
            if all(
                raw_association.get(key)
                for key in ("agreement_id", "confirmed_by", "confirmed_at", "invoice_fingerprint")
            ):
                association = WorkspaceAssociation(
                    agreement_id=raw_association["agreement_id"],
                    version_number=raw_association["version_number"],
                    kind="confirmed",
                    confirmed_by=raw_association["confirmed_by"],
                    confirmed_at=raw_association["confirmed_at"],
                )
            elif linked_identity is not None:
                association = WorkspaceAssociation(
                    agreement_id=linked_identity.id, kind="legacy_identity"
                )
            findings = snapshot.assessment.get("findings", [])
            action: _CaseAction = (
                "view_case"
                if status in ("approved", "rejected")
                else (
                    "review_duplicate"
                    if status == "duplicate"
                    else "review_and_decide" if status == "matched" else "resolve_discrepancies"
                )
            )
            items.append(
                WorkspaceCase(
                    case_id=header.id,
                    version_number=snapshot.version_number,
                    identity=self._identity(header),
                    invoice_number=data.get("invoice_number"),
                    vendor_name=data.get("vendor_name"),
                    location=data.get("location"),
                    status=status,
                    blocking_count=sum(item.get("severity") == "blocking" for item in findings),
                    review_count=sum(item.get("severity") == "review" for item in findings),
                    source_document_id=package["invoice"]["source_document_id"],
                    association=association,
                    created_at=snapshot.created_at,
                    next_action=action,
                )
            )
        return WorkspacePage(
            items=tuple(items), total=total, limit=params.limit, offset=params.offset
        )

    async def contracts(
        self, tenant_id: str, params: WorkspaceQuery
    ) -> WorkspacePage[WorkspaceContract]:
        """List current contracts while retaining the separate latest published revision."""
        return await self._bounded(
            self._contracts(
                _Tenant.validate_python(tenant_id), WorkspaceQuery.model_validate(params)
            ),
        )

    async def _contracts(
        self, tenant_id: str, params: WorkspaceQuery
    ) -> WorkspacePage[WorkspaceContract]:
        published = (
            select(func.max(AgreementApproval.version_number))
            .where(
                AgreementApproval.tenant_id == Agreement.tenant_id,
                AgreementApproval.agreement_id == Agreement.id,
            )
            .correlate(Agreement)
            .scalar_subquery()
        )
        status = case((published == Agreement.latest_version, "approved"), else_="draft")
        query = (
            select(
                Agreement, AgreementVersion, published.label("published"), status.label("status")
            )
            .join(
                AgreementVersion,
                and_(
                    Agreement.tenant_id == AgreementVersion.tenant_id,
                    Agreement.id == AgreementVersion.agreement_id,
                    Agreement.latest_version == AgreementVersion.version_number,
                ),
            )
            .where(Agreement.tenant_id == tenant_id)
        )
        terms = AgreementVersion.draft["terms"]
        query = _search(
            query,
            params.q,
            (
                Agreement.contract_number,
                Agreement.vendor_id,
                Agreement.store_id,
                terms["vendor_name"].as_string(),
                terms["location"].as_string(),
            ),
        )
        if params.status:
            query = query.where(status == params.status)
        rows, total = await self._page(
            query.order_by(AgreementVersion.created_at.desc(), Agreement.id.desc()), params
        )
        ids = [header.id for header, *_ in rows]
        counts: dict[str, int] = {}
        legacy_counts: dict[tuple[str, str, str], int] = {}
        if ids:
            association_id = InvoiceCaseVersion.package["association"]["agreement_id"].as_string()
            count_query = (
                select(association_id, func.count())
                .select_from(InvoiceCase)
                .join(
                    InvoiceCaseVersion,
                    and_(
                        InvoiceCase.tenant_id == InvoiceCaseVersion.tenant_id,
                        InvoiceCase.id == InvoiceCaseVersion.case_id,
                        InvoiceCase.latest_version == InvoiceCaseVersion.version_number,
                    ),
                )
                .where(InvoiceCase.tenant_id == tenant_id, _confirmed(), association_id.in_(ids))
                .group_by(association_id)
            )
            counts = {
                identifier: count
                for identifier, count in (await self._db.execute(count_query)).all()
            }
            identities = [
                (header.vendor_id, header.store_id, header.contract_number) for header, *_ in rows
            ]
            legacy_query = (
                select(
                    InvoiceCase.vendor_id,
                    InvoiceCase.store_id,
                    InvoiceCase.contract_number,
                    func.count(),
                )
                .join(
                    InvoiceCaseVersion,
                    and_(
                        InvoiceCase.tenant_id == InvoiceCaseVersion.tenant_id,
                        InvoiceCase.id == InvoiceCaseVersion.case_id,
                        InvoiceCase.latest_version == InvoiceCaseVersion.version_number,
                    ),
                )
                .where(
                    InvoiceCase.tenant_id == tenant_id,
                    association_id.is_(None),
                    or_(
                        *(
                            and_(
                                InvoiceCase.vendor_id == vendor,
                                InvoiceCase.store_id == store,
                                InvoiceCase.contract_number == contract,
                            )
                            for vendor, store, contract in identities
                        )
                    ),
                )
                .group_by(InvoiceCase.vendor_id, InvoiceCase.store_id, InvoiceCase.contract_number)
            )
            legacy_counts = {
                (vendor, store, contract): count
                for vendor, store, contract, count in (await self._db.execute(legacy_query)).all()
            }
        items = tuple(
            WorkspaceContract(
                agreement_id=header.id,
                version_number=snapshot.version_number,
                identity=self._identity(header),
                vendor_name=snapshot.draft.get("terms", {}).get("vendor_name"),
                location=snapshot.draft.get("terms", {}).get("location"),
                status=current_status,
                approved_version_number=approved,
                linked_case_count=counts.get(header.id, 0),
                legacy_case_count=legacy_counts.get(
                    (header.vendor_id, header.store_id, header.contract_number), 0
                ),
                source_document_ids=tuple(snapshot.draft.get("source_document_ids", ())),
                created_at=snapshot.created_at,
                next_action="view_invoices" if current_status == "approved" else "review_agreement",
            )
            for header, snapshot, approved, current_status in rows
        )
        return WorkspacePage(items=items, total=total, limit=params.limit, offset=params.offset)

    async def documents(
        self, tenant_id: str, params: WorkspaceQuery
    ) -> WorkspacePage[WorkspaceDocument]:
        """Search uploads and link exact saved source references without filename inference."""
        return await self._bounded(
            self._documents(
                _Tenant.validate_python(tenant_id), WorkspaceQuery.model_validate(params)
            ),
        )

    async def _documents(
        self, tenant_id: str, params: WorkspaceQuery
    ) -> WorkspacePage[WorkspaceDocument]:
        archived = IngestionJob.meta["paper_archive"]["archived"].as_boolean()
        query = select(IngestionJob).where(
            IngestionJob.tenant_id == tenant_id,
            IngestionJob.meta["workflow"].as_string() == "paper_extraction",
        )
        if params.job_id:
            query = query.where(IngestionJob.id == params.job_id)
        else:
            query = query.where(archived.is_(True) if params.archived else archived.is_not(True))
        query = _search(
            query,
            params.q,
            (
                IngestionJob.meta["original_filename"].as_string(),
                IngestionJob.meta["document_id"].as_string(),
            ),
        )
        if params.status:
            query = query.where(IngestionJob.status == params.status.upper())
        if params.workflow_status:
            query = query.where(self._document_workflow() == params.workflow_status)
        rows, total = await self._page(
            query.order_by(IngestionJob.created_at.desc(), IngestionJob.id.desc()), params
        )
        source_ids = list(
            {
                job.meta.get("document_id")
                for (job,) in rows
                if job.meta and job.meta.get("document_id")
            }
        )
        links, link_totals = await self._source_links(tenant_id, source_ids)
        items = []
        for (job,) in rows:
            meta = job.meta or {}
            document_id = meta.get("document_id")
            current_links = tuple(links.get(document_id or "", ()))
            state = job.status.value.lower()
            workflow: _DocumentState = (
                "processing"
                if state in ("pending", "processing")
                else "extraction_failed" if state == "failed" else "ready_for_review"
            )
            action: _DocumentAction = (
                "wait_for_extraction"
                if workflow == "processing"
                else (
                    "retry_extraction"
                    if workflow == "extraction_failed"
                    else (
                        "review_agreement"
                        if meta["schema_name"] == "rent_agreement"
                        else "review_invoice"
                    )
                )
            )
            if state == "completed" and current_links:
                first = current_links[0]
                workflow = (
                    "invoice_case"
                    if first.kind == "case"
                    else "agreement_approved" if first.status == "approved" else "agreement_draft"
                )
                action = "open_case" if first.kind == "case" else "open_agreement"
            items.append(
                WorkspaceDocument(
                    job_id=job.id,
                    filename=meta["original_filename"],
                    schema_name=meta["schema_name"],
                    status=state,
                    document_id=document_id,
                    archived=(meta.get("paper_archive") or {}).get("archived") is True,
                    created_at=job.created_at,
                    warning_count=meta.get("warning_count", 0),
                    workflow_status=workflow,
                    workflow_links=current_links,
                    workflow_links_total=link_totals.get(document_id or "", 0),
                    workflow_links_resolved=bool(document_id),
                    next_action=action,
                )
            )
        return WorkspacePage(
            items=tuple(items), total=total, limit=params.limit, offset=params.offset
        )

    def _source_values(self) -> Any:
        source_array = AgreementVersion.draft["source_document_ids"]
        if self._db.get_bind().dialect.name == "sqlite":
            return func.json_each(source_array).table_valued("value").alias("source_ids")
        return (
            func.json_array_elements_text(source_array)
            .table_valued("value")
            .render_derived(name="source_ids")
        )

    def _document_workflow(self) -> Any:
        source = IngestionJob.meta["document_id"].as_string()
        values = self._source_values()
        agreement_status = (
            select(
                case(
                    (AgreementApproval.version_number.is_not(None), "agreement_approved"),
                    else_="agreement_draft",
                )
            )
            .select_from(AgreementVersion)
            .join(
                Agreement,
                and_(
                    AgreementVersion.tenant_id == Agreement.tenant_id,
                    AgreementVersion.agreement_id == Agreement.id,
                ),
            )
            .outerjoin(
                AgreementApproval,
                and_(
                    AgreementVersion.tenant_id == AgreementApproval.tenant_id,
                    AgreementVersion.agreement_id == AgreementApproval.agreement_id,
                    AgreementVersion.version_number == AgreementApproval.version_number,
                ),
            )
            .join(values, true())
            .where(AgreementVersion.tenant_id == IngestionJob.tenant_id, values.c.value == source)
            .order_by(
                (AgreementVersion.version_number == Agreement.latest_version).desc(),
                AgreementVersion.version_number.desc(),
                Agreement.id.desc(),
            )
            .limit(1)
            .correlate(IngestionJob)
            .scalar_subquery()
        )
        case_exists = (
            select(InvoiceCaseVersion.case_id)
            .where(
                InvoiceCaseVersion.tenant_id == IngestionJob.tenant_id,
                InvoiceCaseVersion.package["invoice"]["source_document_id"].as_string() == source,
            )
            .correlate(IngestionJob)
            .exists()
        )
        return case(
            (IngestionJob.status.in_(("PENDING", "PROCESSING")), "processing"),
            (IngestionJob.status == "FAILED", "extraction_failed"),
            (agreement_status.is_not(None), agreement_status),
            (case_exists, "invoice_case"),
            else_="ready_for_review",
        )

    async def _source_links(
        self, tenant_id: str, source_ids: list[str]
    ) -> tuple[dict[str, list[WorkspaceLink]], dict[str, int]]:
        if not source_ids:
            return {}, {}
        values = self._source_values()
        agreement_query = (
            select(
                values.c.value.label("source"),
                AgreementVersion.agreement_id.label("id"),
                Agreement.contract_number.label("label"),
                AgreementVersion.version_number.label("version_number"),
                case(
                    (AgreementApproval.version_number.is_not(None), "approved"), else_="draft"
                ).label("status"),
                (AgreementVersion.version_number == Agreement.latest_version).label("is_latest"),
                func.row_number()
                .over(
                    partition_by=(values.c.value, AgreementVersion.agreement_id),
                    order_by=AgreementVersion.version_number.desc(),
                )
                .label("entity_rank"),
            )
            .select_from(AgreementVersion)
            .join(
                Agreement,
                and_(
                    AgreementVersion.tenant_id == Agreement.tenant_id,
                    AgreementVersion.agreement_id == Agreement.id,
                ),
            )
            .outerjoin(
                AgreementApproval,
                and_(
                    AgreementVersion.tenant_id == AgreementApproval.tenant_id,
                    AgreementVersion.agreement_id == AgreementApproval.agreement_id,
                    AgreementVersion.version_number == AgreementApproval.version_number,
                ),
            )
            .join(values, true())
            .where(AgreementVersion.tenant_id == tenant_id, values.c.value.in_(source_ids))
        )
        invoice_source = InvoiceCaseVersion.package["invoice"]["source_document_id"].as_string()
        case_query = (
            select(
                invoice_source.label("source"),
                InvoiceCaseVersion.case_id.label("id"),
                InvoiceCaseVersion.package["invoice"]["fields"]["invoice_number"]
                .as_string()
                .label("label"),
                InvoiceCaseVersion.version_number.label("version_number"),
                _case_status().label("status"),
                (InvoiceCaseVersion.version_number == InvoiceCase.latest_version).label(
                    "is_latest"
                ),
                func.row_number()
                .over(
                    partition_by=(invoice_source, InvoiceCaseVersion.case_id),
                    order_by=InvoiceCaseVersion.version_number.desc(),
                )
                .label("entity_rank"),
            )
            .select_from(InvoiceCaseVersion)
            .join(
                InvoiceCase,
                and_(
                    InvoiceCaseVersion.tenant_id == InvoiceCase.tenant_id,
                    InvoiceCaseVersion.case_id == InvoiceCase.id,
                ),
            )
            .outerjoin(
                InvoiceCaseDecision,
                and_(
                    InvoiceCaseVersion.tenant_id == InvoiceCaseDecision.tenant_id,
                    InvoiceCaseVersion.case_id == InvoiceCaseDecision.case_id,
                    InvoiceCaseVersion.version_number == InvoiceCaseDecision.version_number,
                ),
            )
            .where(InvoiceCaseVersion.tenant_id == tenant_id, invoice_source.in_(source_ids))
        )
        result: dict[str, list[WorkspaceLink]] = {}
        totals: dict[str, int] = {}
        for kind, raw_query in (("agreement", agreement_query), ("case", case_query)):
            candidates = raw_query.subquery()
            latest = select(candidates).where(candidates.c.entity_rank == 1).subquery()
            bounded = select(
                latest,
                func.count().over(partition_by=latest.c.source).label("total"),
                func.row_number()
                .over(
                    partition_by=latest.c.source,
                    order_by=(
                        latest.c.is_latest.desc(),
                        latest.c.version_number.desc(),
                        latest.c.id.desc(),
                    ),
                )
                .label("source_rank"),
            ).subquery()
            rows = (
                (
                    await self._db.execute(
                        select(bounded).where(bounded.c.source_rank <= _LINK_LIMIT)
                    )
                )
                .mappings()
                .all()
            )
            seen_totals: dict[str, int] = {}
            for row in rows:
                source = row["source"]
                result.setdefault(source, []).append(
                    WorkspaceLink(
                        kind=cast(Literal["agreement", "case"], kind),
                        id=row["id"],
                        version_number=row["version_number"],
                        status=row["status"],
                        is_latest=row["is_latest"],
                        label=row["label"],
                    )
                )
                seen_totals[source] = row["total"]
            for source, count in seen_totals.items():
                totals[source] = totals.get(source, 0) + count
        return {source: items[:_LINK_LIMIT] for source, items in result.items()}, totals

    @staticmethod
    def _identity(header: Any) -> AgreementIdentity:
        return AgreementIdentity(
            vendor_id=header.vendor_id,
            store_id=header.store_id,
            contract_number=header.contract_number,
        )
