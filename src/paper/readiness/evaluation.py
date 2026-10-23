"""Pure prerequisite evaluation sharing actual reconciliation requirements."""

from typing import Literal

from src.paper.association.confirmation import AssociationConfirmation
from src.paper.reconciliation.contracts import InvoicePackage, ReconciliationAssessment
from src.paper.reconciliation.fingerprints import package_fingerprint
from src.paper.reconciliation.settings import ReconciliationSettings

from ._schemas import DocumentRole
from .check import ReadinessCheck
from .requirements import documents_by_role, effective_requirements, has_value, requirement_active
from .result import ReadinessResult

_PATHS: dict[DocumentRole, str] = {
    "rent_invoice": "invoice",
    "tax_invoice": "tax_invoices",
    "utility_statement": "utility_statements",
    "supporting_document": "supporting_documents",
}
_AUTHORITY_CODES = frozenset(
    {
        "agreement_missing",
        "agreement_coverage_missing",
        "agreement_version_change",
        "contract_association_invalid",
    }
)


def evaluate(
    package: InvoicePackage,
    assessment: ReconciliationAssessment,
    settings: ReconciliationSettings,
) -> ReadinessResult:
    """Explain missing prerequisites without treating ordinary differences as unreadiness.

    Args:
        package: Exact selected source documents and trusted association provenance.
        assessment: Actual deterministic engine preview with resolved approved authority.
        settings: Host-owned policy used by that engine, never model instructions.

    Returns:
        Policy-bound checks; readiness permits comparison and never AP approval.

    Raises:
        ValueError: The assessment belongs to another package or named policy.
    """
    from src.paper.association.fingerprints import invoice_fingerprint

    package = InvoicePackage.model_validate(package.model_dump(mode="json"))
    assessment = ReconciliationAssessment.model_validate(assessment.model_dump(mode="json"))
    settings = ReconciliationSettings.model_validate(settings.model_dump(mode="json"))
    if assessment.package_fingerprint != package_fingerprint(package) or (
        assessment.policy_id,
        assessment.policy_version,
    ) != (settings.policy_id, settings.policy_version):
        raise ValueError("Readiness requires an assessment of the exact package and host policy.")

    checks: list[ReadinessCheck] = []
    roles = documents_by_role(package)
    missing_paths = {
        item.field_path
        for item in assessment.findings
        if item.severity == "blocking" and item.code.startswith("missing_")
    }
    association = package.association
    confirmed = isinstance(association, AssociationConfirmation) and (
        association.invoice_fingerprint
        == invoice_fingerprint(package.invoice, package.review_context)
    )
    if (
        isinstance(association, AssociationConfirmation)
        and confirmed
        and assessment.agreement_reference is not None
    ):
        confirmed = (
            association.agreement_id == assessment.agreement_reference.agreement_id
            and association.version_number == assessment.agreement_reference.version_number
        )
    checks.append(
        ReadinessCheck(
            kind="authority",
            label="Confirmed contract association",
            requirement="required",
            status="satisfied" if confirmed else "missing",
            blocking=not confirmed,
            reason="The reviewer must confirm the exact approved contract for this invoice.",
            field_path="/association",
            source_document_ids=(package.invoice.source_document_id,),
            code="contract_association_required",
        )
    )
    authority = assessment.agreement_reference is not None
    checks.append(
        ReadinessCheck(
            kind="authority",
            label="Approved service-period authority",
            requirement="required",
            status="satisfied" if authority else "missing",
            blocking=not authority,
            reason="An approved contract must cover the source service dates or explicit approved installment allocation.",
            field_path="/agreement",
            code="approved_authority_required",
        )
    )

    for role, documents in roles.items():
        role_requirements = tuple(item for item in settings.field_requirements if item.role == role)
        field_requires_document = any(
            requirement_active(item, package) for item in role_requirements
        )
        required = role in settings.required_documents or field_requires_document
        # The engine owns explicit approved withholding substitution for tax documents.
        substituted = required and not documents and f"/{role}" not in missing_paths
        checks.append(
            ReadinessCheck(
                kind="document",
                role=role,
                field_path=f"/{role}",
                label=role.replace("_", " ").capitalize(),
                requirement="required" if required else "optional",
                status=(
                    "satisfied"
                    if documents or substituted
                    else "missing" if required else "not_applicable"
                ),
                blocking=required and not documents and not substituted,
                reason=(
                    "The engine accepted the approved alternative document path."
                    if substituted
                    else (
                        "Select the reviewed documents required by the host policy."
                        if required
                        else "This document role is optional unless an active field or accounting rule requires it."
                    )
                ),
                source_document_ids=tuple(item.source_document_id for item in documents),
            )
        )
        for index, document in enumerate(documents or (None,)):
            field_requirements = (
                effective_requirements(settings, role)
                if document is not None
                else role_requirements
            )
            for requirement in field_requirements:
                path = (
                    f"/invoice/fields/{requirement.field}"
                    if role == "rent_invoice"
                    else f"/{_PATHS[role]}/{index}/fields/{requirement.field}"
                )
                active = requirement_active(requirement, package, document)
                value = (
                    getattr(document.fields, requirement.field) if document is not None else None
                )
                present = has_value(value)
                reason = requirement.reason
                substituted_field = False
                if role == "rent_invoice" and active and not present and path not in missing_paths:
                    if (
                        requirement.field in ("vendor_id", "store_id", "contract_number")
                        and confirmed
                    ):
                        substituted_field = True
                        reason += " The confirmed master assignment supplies routing identity; the source field remains absent."
                    elif (
                        requirement.field in ("service_period_start", "service_period_end")
                        and package.review_context is not None
                        and authority
                    ):
                        substituted_field = True
                        reason += " The separately reviewed approved installment allocation supplies coverage; no source date is invented."
                    elif (
                        requirement.field == "tax_amount"
                        and package.invoice.fields.vat_amount is not None
                        and package.invoice.fields.withholding_amount is not None
                    ):
                        substituted_field = True
                        reason += " Separate explicit VAT and withholding components supply the payment breakdown."
                satisfied = present or substituted_field
                status: Literal["satisfied", "missing", "not_applicable"] = (
                    "not_applicable"
                    if requirement.requirement == "conditional" and not active
                    else "satisfied" if satisfied else "missing" if active else "not_applicable"
                )
                checks.append(
                    ReadinessCheck(
                        kind="field",
                        role=role,
                        field=requirement.field,
                        field_path=path,
                        label=requirement.field.replace("_", " ").capitalize(),
                        requirement=requirement.requirement,
                        status=status,
                        blocking=active and not satisfied,
                        reason=reason,
                        source_document_ids=(
                            (document.source_document_id,) if document is not None else ()
                        ),
                    )
                )

    for required_type in settings.required_supporting_types:
        matching = tuple(
            item.source_document_id
            for item in package.supporting_documents
            if item.fields.document_type == required_type
        )
        checks.append(
            ReadinessCheck(
                kind="document",
                role="supporting_document",
                label="Required supporting type",
                requirement="required",
                status="satisfied" if matching else "missing",
                blocking=not matching,
                reason=f"Host policy requires supporting document type: {required_type}.",
                field_path="/supporting_documents",
                source_document_ids=matching,
                code="required_supporting_type",
            )
        )
    represented = {item.field_path for item in checks if item.blocking}
    for finding in assessment.findings:
        if finding.severity != "blocking" or not (
            finding.code.startswith("missing_") or finding.code in _AUTHORITY_CODES
        ):
            continue
        if (
            finding.code in ("missing_field", "missing_document")
            and finding.field_path in represented
        ):
            continue
        if finding.code == "agreement_missing" and not authority:
            # The coverage prerequisite above represents this unchanged engine diagnostic.
            continue
        guard_field = (
            finding.field_path.rsplit("/", 1)[-1]
            if finding.field_path is not None and "/fields/" in finding.field_path
            else None
        )
        guard_role = next(
            (
                role
                for role, prefix in _PATHS.items()
                if finding.field_path is not None and finding.field_path.startswith(f"/{prefix}/")
            ),
            None,
        )
        guard_reason = finding.message
        if (
            finding.code == "missing_field"
            and guard_role == "rent_invoice"
            and guard_field in ("service_period_start", "service_period_end")
        ):
            guard_reason = "Source service dates or a reviewed approved installment allocation are required to establish contract coverage. Optional presence configuration cannot waive this accounting guard."
        checks.append(
            ReadinessCheck(
                kind="authority" if finding.code in _AUTHORITY_CODES else "accounting",
                role=guard_role,
                field=guard_field,
                label=(
                    guard_field
                    if finding.code == "missing_field" and guard_field is not None
                    else finding.code
                )
                .replace("_", " ")
                .capitalize(),
                requirement="required",
                status="missing",
                blocking=True,
                reason=guard_reason,
                field_path=finding.field_path,
                source_document_ids=finding.source_document_ids,
                code=finding.code,
            )
        )
    if assessment.outcome == "incomplete" and not any(item.blocking for item in checks):
        checks.append(
            ReadinessCheck(
                kind="accounting",
                label="Reconciliation prerequisites",
                requirement="required",
                status="missing",
                blocking=True,
                reason="The actual reconciliation engine still reports incomplete prerequisites.",
                code="assessment_incomplete",
            )
        )
    return ReadinessResult(
        ready=not any(item.blocking for item in checks),
        policy_id=assessment.policy_id,
        policy_version=assessment.policy_version,
        policy_fingerprint=assessment.policy_fingerprint,
        package_fingerprint=assessment.package_fingerprint,
        checks=tuple(checks),
    )
