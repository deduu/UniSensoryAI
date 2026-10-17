"""Versioned exact-decimal withholding checks independent of models and tax law."""

from decimal import ROUND_DOWN, ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal, localcontext

from src.paper.contracts import AgreementVersion

from .contracts import InvoicePackage, ReconciliationFinding
from .ports.rule import BaseReconciliationRule
from .settings import ReconciliationSettings

_ROUNDING = {"down": ROUND_DOWN, "half_up": ROUND_HALF_UP, "half_even": ROUND_HALF_EVEN}


class WithholdingReconciliationRule(BaseReconciliationRule):
    """Apply only the rate and rounding explicitly present in approved authority."""

    @property
    def rule_id(self) -> str:
        """Return the stable withholding rule identifier."""
        return "paper.withholding"

    @property
    def rule_version(self) -> str:
        """Return the behavioral version included in assessment fingerprints."""
        return "1"

    def evaluate(
        self,
        package: InvoicePackage,
        *,
        agreement: AgreementVersion | None,
        settings: ReconciliationSettings,
    ) -> tuple[ReconciliationFinding, ...]:
        """Check explicit components and bounded source rounding without tax inference."""
        invoice = package.invoice.fields
        policy = agreement.draft.terms.withholding_policy if agreement is not None else None
        structured = invoice.vat_amount is not None or invoice.withholding_amount is not None
        if not structured and policy is None and invoice.rounding_adjustment is None:
            return ()
        findings: list[ReconciliationFinding] = []

        def add(code: str, message: str, field: str) -> None:
            findings.append(
                ReconciliationFinding(
                    code=code,
                    severity="blocking",
                    message=message,
                    source_document_ids=(package.invoice.source_document_id,),
                    field_path=f"/invoice/fields/{field}",
                )
            )

        for name in ("subtotal", "total", "currency"):
            if getattr(invoice, name) is None:
                add(
                    f"missing_component_{name}",
                    "Structured payment reconciliation requires explicit gross rent, net payable, and currency.",
                    name,
                )
        if invoice.total is not None and Decimal(invoice.total) < 0:
            add(
                "unsupported_negative_payable",
                "Negative net payable requires a separately configured credit or refund policy.",
                "total",
            )
        if (
            invoice.subtotal is not None
            and invoice.withholding_amount is not None
            and Decimal(invoice.withholding_amount) > Decimal(invoice.subtotal)
        ):
            add(
                "unsupported_withholding_amount",
                "The positive-rent withholding rule cannot deduct more than the gross rent.",
                "withholding_amount",
            )

        for name in ("vat_amount", "withholding_amount"):
            if getattr(invoice, name) is None:
                add(
                    f"missing_{name}",
                    "Explicit VAT and withholding components are required by this reconciliation path.",
                    name,
                )
        if invoice.withholding_amount is not None and Decimal(invoice.withholding_amount) > 0:
            if invoice.invoice_number is None:
                add(
                    "missing_withholding_invoice_reference",
                    "A primary invoice number is required to bind withholding evidence to this invoice.",
                    "invoice_number",
                )
            required_fields = (
                "reference_number",
                "document_date",
                "invoice_number",
                "vendor_id",
                "store_id",
                "contract_number",
                "currency",
                "total",
            )
            documents = [
                document
                for document in package.supporting_documents
                if document.fields.document_type in settings.withholding_required_supporting_types
            ]
            references = [
                document.fields.reference_number
                for document in documents
                if document.fields.reference_number is not None
            ]
            if len(set(references)) != len(references):
                add(
                    "duplicate_withholding_evidence",
                    "Withholding evidence repeats a certificate reference; duplicate evidence cannot establish a deduction.",
                    "withholding_amount",
                )
            for required_type in settings.withholding_required_supporting_types:
                matching = [
                    document
                    for document in documents
                    if document.fields.document_type == required_type
                ]
                if not matching:
                    add(
                        "missing_withholding_evidence",
                        "A required withholding supporting document type is missing.",
                        "withholding_amount",
                    )
                    continue
                if any(
                    getattr(document.fields, name) is None
                    for document in matching
                    for name in required_fields
                ):
                    add(
                        "missing_withholding_evidence_fields",
                        "Withholding evidence requires its reference, date, invoice identity, canonical vendor/store/contract, currency, and deduction amount.",
                        "withholding_amount",
                    )
                if all(document.fields.total is not None for document in matching):
                    with localcontext() as evidence_context:
                        evidence_context.prec = 256
                        total = sum(
                            (
                                Decimal(document.fields.total)
                                for document in matching
                                if document.fields.total is not None
                            ),
                            Decimal(0),
                        )
                        if total != Decimal(invoice.withholding_amount) or any(
                            Decimal(document.fields.total) < 0
                            for document in matching
                            if document.fields.total is not None
                        ):
                            add(
                                "withholding_evidence_mismatch",
                                "Withholding supporting amounts differ from the explicit invoice deduction.",
                                "withholding_amount",
                            )
        with localcontext() as context:
            context.prec = 256
            adjustment = Decimal(invoice.rounding_adjustment or "0")
            if policy is None:
                if (
                    invoice.withholding_amount is not None
                    and Decimal(invoice.withholding_amount) != 0
                ):
                    add(
                        "missing_withholding_policy",
                        "A positive withholding deduction requires an explicitly approved rate and rounding policy.",
                        "withholding_amount",
                    )
                if adjustment != 0:
                    add(
                        "missing_rounding_policy",
                        "A source payable adjustment requires an explicitly approved rounding policy.",
                        "rounding_adjustment",
                    )
                return tuple(findings)
            quantum = Decimal(1).scaleb(-policy.decimal_places)
            if abs(adjustment) > quantum:
                add(
                    "rounding_adjustment_exceeds_policy",
                    "The source payable adjustment exceeds the approved rounding quantum.",
                    "rounding_adjustment",
                )
            if invoice.subtotal is None:
                add(
                    "missing_withholding_base",
                    "Gross rent is required to assess the approved withholding policy.",
                    "subtotal",
                )
            elif Decimal(invoice.subtotal) < 0:
                add(
                    "unsupported_withholding_base",
                    "Negative gross rent requires a separately configured adjustment policy.",
                    "subtotal",
                )
            elif invoice.withholding_amount is not None:
                expected = (Decimal(invoice.subtotal) * Decimal(policy.rate)).quantize(
                    quantum, rounding=_ROUNDING[policy.rounding_mode]
                )
                if Decimal(invoice.withholding_amount) != expected:
                    add(
                        "withholding_amount_mismatch",
                        "The withholding amount differs from the approved rate and exact rounding policy.",
                        "withholding_amount",
                    )
        return tuple(findings)
