"""Resolve reviewer selections through injected storage before deterministic matching."""

import asyncio
from typing import TYPE_CHECKING, Any

from src.paper.contracts import AgreementActor
from src.paper.errors import AgreementMasterError
from src.paper.readiness import ReadinessResult, evaluate
from src.paper.reconciliation.contracts import InvoiceCaseVersion, InvoicePackage
from src.paper.reconciliation.settings import ReconciliationSettings
from src.paper.reconciliation.workflow import InvoiceCaseService

from .request import PrepareCaseRequest
from .selected_version import SelectedDocumentVersion

if TYPE_CHECKING:
    from src.services.paper_document_drafts import DocumentDraftService


class CasePreparationService:
    """Bind exact reviewed snapshots and recheck readiness on every explicit run.

    Args:
        drafts: Tenant-scoped document draft service, supplied by the host.
        cases: Existing case workflow and approved agreement resolution.
        settings: Validated host-owned requirements; never supplied by a model.
    """

    def __init__(
        self,
        drafts: "DocumentDraftService",
        cases: InvoiceCaseService,
        settings: ReconciliationSettings,
    ) -> None:
        self._drafts = drafts
        self._cases = cases
        self._settings = ReconciliationSettings.model_validate(settings)

    async def resolve(
        self, *, actor: AgreementActor, request: PrepareCaseRequest
    ) -> InvoicePackage:
        """Read exact, reviewed versions sequentially within the shared transaction."""
        try:
            return await asyncio.wait_for(self._resolve(actor=actor, request=request), timeout=15)
        except asyncio.TimeoutError:
            raise AgreementMasterError(
                "timeout", "Selected document lookup exceeded its deadline."
            ) from None

    async def _resolve(
        self, *, actor: AgreementActor, request: PrepareCaseRequest
    ) -> InvoicePackage:
        actor = AgreementActor.model_validate(actor)
        request = PrepareCaseRequest.model_validate(request)
        documents: dict[str, Any] = {}
        provenance = []
        source_ids: set[str] = set()
        roles = (
            ("rent_invoice", "invoice", (request.invoice,)),
            ("tax_invoice", "tax_invoices", request.tax_invoices),
            ("utility_statement", "utility_statements", request.utility_statements),
            ("supporting_document", "supporting_documents", request.supporting_documents),
        )
        for role, key, references in roles:
            selected = []
            for reference in references:
                record = await self._drafts.get_version(
                    actor=actor,
                    draft_id=reference.draft_id,
                    version_number=reference.version_number,
                )
                if (
                    record.tenant_id != actor.tenant_id
                    or record.draft_id != reference.draft_id
                    or record.version_number != reference.version_number
                    or record.role != role
                    or record.status != "reviewed"
                    or not record.reviewed_by
                    or not record.reviewed_at
                ):
                    raise AgreementMasterError(
                        "invalid_agreement",
                        "Select an exact reviewed document version in this tenant.",
                    )
                if record.document.source_document_id in source_ids:
                    raise AgreementMasterError(
                        "invalid_agreement", "Select documents with distinct source identifiers."
                    )
                source_ids.add(record.document.source_document_id)
                selected.append(record.document)
                provenance.append(
                    SelectedDocumentVersion(
                        draft_id=record.draft_id,
                        version_number=record.version_number,
                        role=record.role,
                        source_document_id=record.document.source_document_id,
                        reviewed_by=record.reviewed_by,
                        reviewed_at=record.reviewed_at,
                    )
                )
            documents[key] = selected[0] if key == "invoice" else tuple(selected)
        return InvoicePackage(
            identity=request.identity,
            association=request.association,
            review_context=request.review_context,
            document_draft_references=tuple(provenance),
            **documents,
        )

    async def check(self, *, actor: AgreementActor, request: PrepareCaseRequest) -> ReadinessResult:
        """Compute current requirements and authority without saving an assessment."""
        package = await self.resolve(actor=actor, request=request)
        confirmed, assessment = await self._cases.preview_assessment(actor=actor, package=package)
        return evaluate(confirmed, assessment, self._settings)

    async def reconcile(
        self, *, actor: AgreementActor, request: PrepareCaseRequest
    ) -> InvoiceCaseVersion:
        """Revalidate selected documents and readiness, then append a case assessment."""
        readiness = await self.check(actor=actor, request=request)
        if not readiness.ready:
            raise AgreementMasterError(
                "invalid_agreement",
                "Case readiness is incomplete; resolve the missing prerequisites.",
            )
        package = await self.resolve(actor=actor, request=request)
        if request.case_id is not None and request.expected_version is not None:
            result = await self._cases.revise_case(
                actor=actor,
                case_id=request.case_id,
                expected_version=request.expected_version,
                package=package,
            )
        else:
            result = await self._cases.create_case(actor=actor, package=package)
        # A changed authority between preview and storage must roll back this run.
        if not evaluate(result.package, result.assessment, self._settings).ready:
            raise AgreementMasterError(
                "conflict", "Case readiness changed; check the selected documents again."
            )
        return result
