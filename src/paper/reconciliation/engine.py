"""Deterministic PAPER.ID checks without model, database, or external I/O."""

import calendar
from decimal import Decimal, localcontext
from typing import Literal

from pydantic import TypeAdapter, ValidationError

from src.paper.association.confirmation import AssociationConfirmation
from src.paper.association.fingerprints import invoice_fingerprint
from src.paper.contracts import AgreementVersion
from src.paper.contracts._base import Identifier
from src.paper.errors import AgreementMasterError
from src.paper.readiness._schemas import DocumentRole
from src.paper.readiness.requirements import (
    documents_by_role,
    required_field_names,
    requirement_active,
)
from src.paper.schemas import RentInvoiceSchema

from .billing import billing_period
from .contracts import (
    AgreementReference,
    InvoicePackage,
    ReconciliationAssessment,
    ReconciliationFinding,
    RentInvoiceDocument,
    SupportingDocument,
    TaxInvoiceDocument,
    UtilityStatementDocument,
)
from .fingerprints import package_fingerprint, policy_fingerprint
from .ports.rule import BaseReconciliationRule
from .settings import ReconciliationSettings

_IDENTIFIER = TypeAdapter(Identifier)
_INCOMPLETE_CODES = frozenset(
    {"agreement_missing", "agreement_coverage_missing", "agreement_version_change"}
)


class _Findings:
    def __init__(self) -> None:
        self.values: list[ReconciliationFinding] = []

    def add(
        self,
        code: str,
        message: str,
        *,
        sources: tuple[str, ...] = (),
        field_path: str | None = None,
        severity: Literal["blocking", "review"] = "blocking",
    ) -> None:
        self.values.append(
            ReconciliationFinding(
                code=code,
                severity=severity,
                message=message,
                source_document_ids=sources,
                field_path=field_path,
            )
        )

    def outcome(self) -> Literal["matched", "incomplete", "mismatched", "needs_review"]:
        if any(
            item.severity == "blocking"
            and (item.code.startswith("missing_") or item.code in _INCOMPLETE_CODES)
            for item in self.values
        ):
            return "incomplete"
        if any(item.severity == "blocking" for item in self.values):
            return "mismatched"
        return "needs_review" if self.values else "matched"


class ReconciliationEngine:
    """Assess source fields against one approved agreement and host requirements.

    The engine cannot approve cases or infer accounting/tax policy. Required
    fields and supporting documents are host configurable. Fixed amounts are
    comparable only using an explicit approved or host billing basis.
    """

    def __init__(
        self,
        settings: ReconciliationSettings,
        extra_rules: tuple[BaseReconciliationRule, ...] = (),
    ) -> None:
        """Inject host policy and optional synchronous, versioned business rules."""
        self._settings = ReconciliationSettings.model_validate(settings.model_dump(mode="json"))
        if len(extra_rules) > 64:
            raise ValueError("Reconciliation rule budget exceeded.")
        rule_versions = tuple(
            (
                _IDENTIFIER.validate_python(rule.rule_id),
                _IDENTIFIER.validate_python(rule.rule_version),
            )
            for rule in extra_rules
        )
        if len({rule_id for rule_id, _ in rule_versions}) != len(rule_versions):
            raise ValueError("Reconciliation rule identifiers must be unique.")
        self._extra_rules = extra_rules
        self._rule_ids = frozenset(rule_id for rule_id, _ in rule_versions)
        self._settings_fingerprint = policy_fingerprint(self._settings)
        self._policy_fingerprint = policy_fingerprint(self._settings, rule_versions)

    @property
    def settings_fingerprint(self) -> str:
        """Return the base host settings hash independently of extra rule versions."""
        return self._settings_fingerprint

    @property
    def policy_fingerprint(self) -> str:
        """Return the policy hash including versioned injected rules."""
        return self._policy_fingerprint

    def assess(
        self,
        package: InvoicePackage,
        *,
        agreement_start: AgreementVersion | None,
        agreement_end: AgreementVersion | None,
        tenant_id: str,
    ) -> ReconciliationAssessment:
        """Return deterministic findings bound to the exact package and policy.

        Args:
            package: Validated source documents with canonical agreement identity.
            agreement_start: Approved authority effective on the first service day.
            agreement_end: Approved authority effective on the final service day.
            tenant_id: Trusted host tenant used to qualify all authority references.

        Returns:
            A persistable advisory assessment; AP approval remains a separate act.

        Raises:
            AgreementMasterError: An adapter supplies unscoped or unapproved authority.
        """
        package = InvoicePackage.model_validate(package.model_dump(mode="json"))
        tenant_id = _IDENTIFIER.validate_python(tenant_id)
        findings = _Findings()
        authority_findings = _Findings()
        agreement = self._authority(
            package, agreement_start, agreement_end, tenant_id, authority_findings
        )
        if package.association is not None and not self._confirmed_association(package, agreement):
            findings.add(
                "contract_association_invalid",
                "Contract association is unconfirmed, changed, or disagrees with approved authority.",
                sources=(package.invoice.source_document_id,),
                field_path="/association",
            )
        self._requirements(package, findings, agreement)
        findings.values.extend(authority_findings.values)
        self._rule_guards(package, agreement, findings)
        self._references(package, agreement, findings)
        with localcontext() as context:
            # Schema decimal strings are bounded to 100 characters; exact sums of
            # all 100 package documents fit comfortably within this precision.
            context.prec = 256
            self._amounts(package, findings)
            if agreement is not None:
                self._pricing(
                    package.invoice.fields, agreement, findings, package.invoice.source_document_id
                )
        for rule in self._extra_rules:
            rule_findings = rule.evaluate(package, agreement=agreement, settings=self._settings)
            if not isinstance(rule_findings, tuple) or len(rule_findings) > 100:
                raise AgreementMasterError(
                    "invalid_configuration", "A reconciliation rule exceeded its finding budget."
                ) from None
            findings.values.extend(
                ReconciliationFinding.model_validate(finding) for finding in rule_findings
            )
        reference = None
        if agreement is not None and agreement.approval is not None:
            reference = AgreementReference(
                agreement_id=agreement.agreement_id,
                version_number=agreement.version_number,
                classification=agreement.approval.classification,
            )
        return ReconciliationAssessment(
            outcome=findings.outcome(),
            findings=tuple(findings.values),
            agreement_reference=reference,
            policy_id=self._settings.policy_id,
            policy_version=self._settings.policy_version,
            policy_fingerprint=self._policy_fingerprint,
            package_fingerprint=package_fingerprint(package),
        )

    def _rule_guards(
        self, package: InvoicePackage, agreement: AgreementVersion | None, findings: _Findings
    ) -> None:
        invoice = package.invoice.fields
        terms = agreement.draft.terms if agreement is not None else None
        if (
            invoice.installment_id is not None
            or package.review_context is not None
            or (terms is not None and terms.installment_schedule is not None)
        ) and "paper.installment_schedule" not in self._rule_ids:
            findings.add(
                "missing_installment_rule",
                "Explicit installment data requires an installed versioned installment rule.",
            )
        if (
            invoice.vat_amount is not None
            or invoice.withholding_amount is not None
            or invoice.rounding_adjustment is not None
            or (terms is not None and terms.withholding_policy is not None)
        ) and "paper.withholding" not in self._rule_ids:
            findings.add(
                "missing_withholding_rule",
                "Explicit payment components require an installed versioned withholding rule.",
            )

    @staticmethod
    def _confirmed_association(
        package: InvoicePackage,
        agreement: AgreementVersion | None,
    ) -> bool:
        association = package.association
        return isinstance(association, AssociationConfirmation) and (
            association.invoice_fingerprint
            == invoice_fingerprint(package.invoice, package.review_context)
            and (
                agreement is None
                or (
                    association.agreement_id == agreement.agreement_id
                    and association.version_number == agreement.version_number
                )
            )
        )

    def _requirements(
        self, package: InvoicePackage, findings: _Findings, agreement: AgreementVersion | None
    ) -> None:
        roles = documents_by_role(package)
        invoice = package.invoice.fields
        withholding_evidence = (
            self._settings.allow_withholding_without_vat_invoice
            and "paper.withholding" in self._rule_ids
            and agreement is not None
            and agreement.draft.terms.withholding_policy is not None
            and invoice.vat_amount is not None
            and Decimal(invoice.vat_amount) == 0
            and invoice.withholding_amount is not None
            and Decimal(invoice.withholding_amount) > 0
        )
        for role in self._settings.required_documents:
            if (
                role == "tax_invoice"
                and withholding_evidence
                and not any(
                    item.role == role and requirement_active(item, package)
                    for item in self._settings.field_requirements
                )
            ):
                continue
            if not roles[role]:
                findings.add(
                    "missing_document",
                    "A required document role is missing.",
                    field_path=f"/{role}",
                )
        for role in ("tax_invoice", "utility_statement", "supporting_document"):
            if (
                role not in self._settings.required_documents
                and not roles[role]
                and any(
                    item.role == role and requirement_active(item, package)
                    for item in self._settings.field_requirements
                )
            ):
                findings.add(
                    "missing_document",
                    "An active field requirement needs a selected document of this role.",
                    field_path=f"/{role}",
                )
        types = {document.fields.document_type for document in package.supporting_documents}
        required_types = (
            *self._settings.required_supporting_types,
            *(self._settings.withholding_required_supporting_types if withholding_evidence else ()),
        )
        for required_type in dict.fromkeys(required_types):
            if required_type not in types:
                findings.add(
                    "missing_document",
                    "A required supporting document type is missing.",
                    field_path="/supporting_documents",
                )
        invoice_fields = tuple(
            dict.fromkeys(
                (
                    *required_field_names(self._settings, "rent_invoice", package, package.invoice),
                    "service_period_start",
                    "service_period_end",
                )
            )
        )
        for name in invoice_fields:
            if (
                name in ("vendor_id", "store_id", "contract_number")
                and self._confirmed_association(package, agreement)
                and getattr(package.invoice.fields, name) is None
            ):
                # Assigned master IDs satisfy this routing requirement without
                # pretending the source PDF printed those internal identifiers.
                continue
            if (
                name in ("service_period_start", "service_period_end")
                and package.review_context is not None
                and invoice.service_period_start is None
                and invoice.service_period_end is None
                and "paper.installment_schedule" in self._rule_ids
                and agreement is not None
                and agreement.draft.terms.installment_schedule is not None
            ):
                continue
            if (
                name == "tax_amount"
                and invoice.vat_amount is not None
                and invoice.withholding_amount is not None
            ):
                continue
            value = getattr(package.invoice.fields, name)
            if value is None or value == "" or value == () or value == {}:
                findings.add(
                    "missing_field",
                    "A required invoice field is missing.",
                    sources=(package.invoice.source_document_id,),
                    field_path=f"/invoice/fields/{name}",
                )
        for index, tax in enumerate(package.tax_invoices):
            for name in required_field_names(self._settings, "tax_invoice", package, tax):
                value = getattr(tax.fields, name)
                if value is None or value == "" or value == () or value == {}:
                    findings.add(
                        "missing_field",
                        "A required tax document field is missing.",
                        sources=(tax.source_document_id,),
                        field_path=f"/tax_invoices/{index}/fields/{name}",
                    )
        extra_roles: dict[DocumentRole, str] = {
            "utility_statement": "utility_statements",
            "supporting_document": "supporting_documents",
        }
        for role, path in extra_roles.items():
            for index, document in enumerate(roles[role]):
                for name in required_field_names(self._settings, role, package, document):
                    value = getattr(document.fields, name)
                    if value is None or value == "" or value == () or value == {}:
                        findings.add(
                            "missing_field",
                            "An active host requirement needs this source document field.",
                            sources=(document.source_document_id,),
                            field_path=f"/{path}/{index}/fields/{name}",
                        )
        for warning_document in (
            package.invoice,
            *package.tax_invoices,
            *package.utility_statements,
            *package.supporting_documents,
        ):
            if warning_document.warnings:
                findings.add(
                    "extraction_warnings",
                    "Extraction diagnostics require reviewer acknowledgement.",
                    sources=(warning_document.source_document_id,),
                    severity="review",
                )

    def _authority(
        self,
        package: InvoicePackage,
        start: AgreementVersion | None,
        end: AgreementVersion | None,
        tenant_id: str,
        findings: _Findings,
    ) -> AgreementVersion | None:
        try:
            start = (
                AgreementVersion.model_validate(start.model_dump(mode="json"))
                if start is not None
                else None
            )
            end = (
                AgreementVersion.model_validate(end.model_dump(mode="json"))
                if end is not None
                else None
            )
        except (ValidationError, AttributeError):
            raise AgreementMasterError(
                "invalid_agreement", "Agreement authority is invalid."
            ) from None
        for reference in (start, end):
            if reference is not None and (
                reference.tenant_id != tenant_id
                or reference.identity != package.identity
                or reference.approval is None
            ):
                raise AgreementMasterError(
                    "invalid_agreement", "Agreement authority does not match the trusted context."
                ) from None
        if start is None or end is None:
            findings.add(
                "agreement_missing",
                "Approved agreement authority is unavailable for the service period.",
            )
            return None
        if (start.agreement_id, start.version_number) != (end.agreement_id, end.version_number):
            findings.add(
                "agreement_version_change",
                "Service period spans different approved agreement versions.",
            )
            return None
        if start.draft != end.draft or (
            start.approval is not None
            and end.approval is not None
            and start.approval.model_dump(exclude={"approved_at"})
            != end.approval.model_dump(exclude={"approved_at"})
        ):
            raise AgreementMasterError(
                "invalid_agreement", "Agreement authority has inconsistent version content."
            ) from None
        source_fields = package.invoice.fields
        first, last = source_fields.service_period_start, source_fields.service_period_end
        if (
            first is None
            and last is None
            and package.review_context is not None
            and start.draft.terms.installment_schedule is None
        ):
            findings.add(
                "missing_installment_schedule",
                "Reviewed advance-rent allocation requires an explicit approved installment schedule.",
            )
        if (
            "paper.installment_schedule" in self._rule_ids
            and start.draft.terms.installment_schedule is not None
        ):
            first, last = billing_period(package)
        if first is None or last is None:
            return None
        if not (start.draft.effective_from <= first <= last <= start.draft.effective_to):
            findings.add(
                "agreement_coverage_missing",
                "The approved agreement does not cover the complete service period.",
            )
            return None
        if start.draft.terms.currency is None:
            findings.add(
                "missing_field",
                "Approved agreement currency is unavailable.",
                sources=start.draft.source_document_ids,
                field_path="/agreement/terms/currency",
            )
        return start

    def _references(
        self, package: InvoicePackage, agreement: AgreementVersion | None, findings: _Findings
    ) -> None:
        invoice = package.invoice.fields
        documents: tuple[
            RentInvoiceDocument
            | TaxInvoiceDocument
            | UtilityStatementDocument
            | SupportingDocument,
            ...,
        ] = (
            package.invoice,
            *package.tax_invoices,
            *package.utility_statements,
            *package.supporting_documents,
        )
        for document in documents:
            fields = document.fields
            for name in ("vendor_id", "store_id", "contract_number"):
                value = getattr(fields, name, None)
                if value is not None and value != getattr(package.identity, name):
                    findings.add(
                        "identity_mismatch",
                        "A document identifier conflicts with canonical agreement identity.",
                        sources=(document.source_document_id,),
                        field_path=f"/fields/{name}",
                    )
            currency = getattr(fields, "currency", None)
            expected_currency = (
                agreement.draft.terms.currency
                if agreement is not None and agreement.draft.terms.currency is not None
                else invoice.currency
            )
            if (
                currency is not None
                and expected_currency is not None
                and currency != expected_currency
            ):
                findings.add(
                    "currency_mismatch",
                    "A document currency conflicts with the reference currency.",
                    sources=(document.source_document_id,),
                    field_path="/fields/currency",
                )
            if document is not package.invoice:
                number = getattr(fields, "invoice_number", None)
                if (
                    number is not None
                    and invoice.invoice_number is not None
                    and number != invoice.invoice_number
                ):
                    findings.add(
                        "invoice_reference_mismatch",
                        "An attachment references a different invoice.",
                        sources=(document.source_document_id,),
                        field_path="/fields/invoice_number",
                    )
                for name in ("service_period_start", "service_period_end"):
                    value = getattr(fields, name, None)
                    if (
                        value is not None
                        and getattr(invoice, name) is not None
                        and value != getattr(invoice, name)
                    ):
                        findings.add(
                            "period_mismatch",
                            "An attachment service period conflicts with the invoice.",
                            sources=(document.source_document_id,),
                            field_path=f"/fields/{name}",
                        )
            bank = getattr(fields, "bank_account", None)
            if (
                agreement is not None
                and bank is not None
                and agreement.draft.terms.bank_account is not None
                and bank != agreement.draft.terms.bank_account
            ):
                findings.add(
                    "bank_mismatch",
                    "A document bank account conflicts with approved agreement terms.",
                    sources=(document.source_document_id,),
                    field_path="/fields/bank_account",
                )
        if agreement is not None and agreement.draft.terms.bank_account is None:
            findings.add(
                "bank_reference_missing",
                "Approved agreement terms have no bank account reference.",
                severity="review",
            )

    def _different(self, first: str, second: str) -> bool:
        return abs(Decimal(first) - Decimal(second)) > Decimal(self._settings.amount_tolerance)

    def _amounts(self, package: InvoicePackage, findings: _Findings) -> None:
        invoice = package.invoice.fields
        structured = any(
            value is not None
            for value in (
                invoice.vat_amount,
                invoice.withholding_amount,
                invoice.rounding_adjustment,
            )
        )
        amount_documents: tuple[
            RentInvoiceDocument | TaxInvoiceDocument | UtilityStatementDocument, ...
        ] = (package.invoice, *package.tax_invoices, *package.utility_statements)
        for document in amount_documents:
            fields = document.fields
            if document is package.invoice and structured:
                if (
                    invoice.subtotal is not None
                    and invoice.vat_amount is not None
                    and invoice.withholding_amount is not None
                ):
                    expected_adjustment = Decimal(invoice.vat_amount) - Decimal(
                        invoice.withholding_amount
                    )
                    if invoice.tax_amount is not None and expected_adjustment != Decimal(
                        invoice.tax_amount
                    ):
                        findings.add(
                            "tax_component_mismatch",
                            "Legacy signed tax adjustment conflicts with separate VAT and withholding components.",
                            sources=(document.source_document_id,),
                            field_path="/invoice/fields/tax_amount",
                        )
                    expected_total = (
                        Decimal(invoice.subtotal)
                        + expected_adjustment
                        + Decimal(invoice.rounding_adjustment or "0")
                    )
                    if invoice.total is not None and expected_total != Decimal(invoice.total):
                        findings.add(
                            "net_payable_mismatch",
                            "Invoice net payable differs from gross rent plus VAT minus withholding plus the explicit source rounding adjustment.",
                            sources=(document.source_document_id,),
                            field_path="/invoice/fields/total",
                        )
                continue
            subtotal = getattr(fields, "subtotal", getattr(fields, "taxable_amount", None))
            tax, total = fields.tax_amount, fields.total
            if subtotal is not None and tax is not None and total is not None:
                expected = str(Decimal(subtotal) + Decimal(tax))
                if self._different(expected, total):
                    findings.add(
                        "amount_mismatch",
                        "Document total differs from subtotal plus source tax amount.",
                        sources=(document.source_document_id,),
                        field_path="/fields/total",
                    )
        if not package.tax_invoices:
            return
        comparisons = (
            (
                ("subtotal", "taxable_amount"),
                ("vat_amount", "tax_amount"),
                ("gross_plus_vat", "total"),
            )
            if structured
            else (("subtotal", "taxable_amount"), ("tax_amount", "tax_amount"), ("total", "total"))
        )
        for invoice_name, tax_name in comparisons:
            if invoice_name == "gross_plus_vat":
                primary = (
                    str(Decimal(invoice.subtotal) + Decimal(invoice.vat_amount))
                    if invoice.subtotal is not None and invoice.vat_amount is not None
                    else None
                )
            else:
                primary = getattr(package.invoice.fields, invoice_name)
            values = [getattr(document.fields, tax_name) for document in package.tax_invoices]
            if primary is not None and all(value is not None for value in values):
                expected = str(
                    sum((Decimal(value) for value in values if value is not None), Decimal(0))
                )
                if self._different(primary, expected):
                    findings.add(
                        "amount_mismatch",
                        "Aggregated tax documents disagree with the invoice amount.",
                        sources=(
                            package.invoice.source_document_id,
                            *(document.source_document_id for document in package.tax_invoices),
                        ),
                        field_path=f"/invoice/fields/{invoice_name}",
                    )

    def _pricing(
        self,
        invoice: RentInvoiceSchema,
        agreement: AgreementVersion,
        findings: _Findings,
        source_id: str,
    ) -> None:
        terms = agreement.draft.terms
        if terms.installment_schedule is not None:
            # The separately injected rule owns explicit installment comparison.
            # Missing implementations are blocking in _rule_guards.
            return
        if (
            terms.rent_type != "fixed"
            or terms.fixed_rent is None
            or (invoice.subtotal is not None and Decimal(invoice.subtotal) < 0)
        ):
            findings.add(
                "unsupported_pricing",
                "Rent pricing requires a separately configured business rule.",
                severity="review",
            )
            return
        basis = self._settings.fixed_rent_basis
        if basis == "approved_extension":
            approved_basis = terms.extensions.get("fixed_rent_basis")
            if approved_basis not in ("per_invoice", "monthly"):
                findings.add(
                    "pricing_basis_unconfigured",
                    "A fixed-rent billing basis has not been explicitly configured.",
                    severity="review",
                )
                return
            basis = "monthly" if approved_basis == "monthly" else "per_invoice"
        if basis == "disabled":
            findings.add(
                "unsupported_pricing",
                "Automated fixed-rent comparison is disabled by host policy.",
                severity="review",
            )
            return
        if basis == "monthly":
            first, last = invoice.service_period_start, invoice.service_period_end
            if first is None or last is None:
                return
            if (
                first.day != 1
                or (first.year, first.month) != (last.year, last.month)
                or last.day != calendar.monthrange(last.year, last.month)[1]
            ):
                findings.add(
                    "unsupported_pricing",
                    "Monthly fixed rent only supports one complete calendar month.",
                    severity="review",
                )
                return
        if invoice.subtotal is not None and self._different(invoice.subtotal, terms.fixed_rent):
            findings.add(
                "amount_mismatch",
                "Invoice rent differs from the approved fixed amount for this billing basis.",
                sources=(source_id,),
                field_path="/invoice/fields/subtotal",
            )
