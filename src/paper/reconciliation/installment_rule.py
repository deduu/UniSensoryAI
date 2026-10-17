"""Deterministic approved-installment selection without calendar inference."""

from decimal import Decimal, localcontext

from src.paper.contracts import AgreementVersion

from .contracts import InvoicePackage, ReconciliationFinding
from .ports.rule import BaseReconciliationRule
from .settings import ReconciliationSettings


class InstallmentReconciliationRule(BaseReconciliationRule):
    """Compare explicit gross obligations and separately reviewed allocation dates."""

    @property
    def rule_id(self) -> str:
        """Return the stable installment rule identifier."""
        return "paper.installment_schedule"

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
        """Validate a selected obligation; never infer payment prerequisites fulfilled."""
        if agreement is None:
            return ()
        schedule = agreement.draft.terms.installment_schedule
        invoice = package.invoice.fields
        review = package.review_context
        findings: list[ReconciliationFinding] = []

        def add(code: str, message: str, *, review_only: bool = False) -> None:
            findings.append(
                ReconciliationFinding(
                    code=code,
                    severity="review" if review_only else "blocking",
                    message=message,
                    source_document_ids=(package.invoice.source_document_id,),
                    field_path="/invoice/fields/installment_id",
                )
            )

        if schedule is None:
            if invoice.installment_id is not None or review is not None:
                add(
                    "missing_installment_schedule",
                    "The approved agreement has no explicit installment schedule.",
                )
            return tuple(findings)
        if agreement.draft.terms.rent_type != "fixed":
            add(
                "unsupported_installment_pricing",
                "This installment rule supports only explicitly approved fixed rent; variable pricing needs a separate versioned rule.",
            )
        if (
            schedule.currency != agreement.draft.terms.currency
            or schedule.currency != invoice.currency
        ):
            add(
                "schedule_currency_mismatch",
                "The approved schedule currency conflicts with agreement or invoice currency.",
            )
        lease_start = agreement.draft.terms.lease_start_date
        lease_end = agreement.draft.terms.lease_end_date
        if any(
            (lease_start is not None and item.coverage_start < lease_start)
            or (lease_end is not None and item.coverage_end > lease_end)
            for item in schedule.installments
        ):
            add(
                "installment_coverage_mismatch",
                "An approved installment allocation exceeds the stated lease coverage.",
            )
        if invoice.installment_id is None:
            add("missing_installment_id", "An explicit approved installment selection is required.")
            return tuple(findings)
        selected = next(
            (
                item
                for item in schedule.installments
                if item.installment_id == invoice.installment_id
            ),
            None,
        )
        if selected is None:
            add(
                "installment_not_found",
                "The selected installment is absent from the approved schedule.",
            )
            return tuple(findings)
        if (
            not agreement.draft.effective_from
            <= selected.coverage_start
            <= selected.coverage_end
            <= agreement.draft.effective_to
        ):
            add(
                "installment_coverage_mismatch",
                "The selected installment exceeds the chosen approved agreement version coverage.",
            )
        if invoice.subtotal is None:
            add(
                "missing_installment_amount",
                "The invoice gross amount is required for installment reconciliation.",
            )
        else:
            with localcontext() as context:
                context.prec = 256
                if abs(Decimal(invoice.subtotal) - Decimal(selected.gross_amount)) > Decimal(
                    settings.amount_tolerance
                ):
                    add(
                        "installment_amount_mismatch",
                        "The invoice gross amount differs from the selected approved installment.",
                    )
        for name in ("vat_amount", "withholding_amount"):
            if getattr(invoice, name) is None:
                add(
                    f"missing_{name}",
                    "Explicit VAT and withholding components are required for installment reconciliation.",
                )
        source_start, source_end = invoice.service_period_start, invoice.service_period_end
        if review is not None:
            if not set(review.source_document_ids).issubset(agreement.draft.source_document_ids):
                add(
                    "allocation_source_mismatch",
                    "Reviewed allocation references are outside the approved agreement sources.",
                )
            if (review.allocation_start, review.allocation_end) != (
                selected.coverage_start,
                selected.coverage_end,
            ):
                add(
                    "installment_period_mismatch",
                    "Reviewed allocation differs from the selected approved installment coverage.",
                )
            if (source_start is not None or source_end is not None) and (
                source_start,
                source_end,
            ) != (review.allocation_start, review.allocation_end):
                add(
                    "allocation_period_conflict",
                    "Source service dates conflict with the separate reviewed allocation context.",
                )
            add(
                "approved_installment_allocation",
                "A human supplied allocation is being used; source service dates remain independently recorded and require AP acknowledgement.",
                review_only=True,
            )
        elif (
            source_start is not None
            and source_end is not None
            and (source_start, source_end) != (selected.coverage_start, selected.coverage_end)
        ):
            add(
                "installment_period_mismatch",
                "Source service dates differ from the selected approved installment coverage.",
            )
        if selected.conditions:
            add(
                "installment_conditions_review",
                "Payment prerequisites and alternative triggers require explicit human review; this rule does not establish fulfillment or authorize payment.",
                review_only=True,
            )
        if schedule.source_discrepancy_note is not None:
            add(
                "source_pricing_discrepancy",
                "The approved schedule retains a source pricing discrepancy requiring explicit AP acknowledgement.",
                review_only=True,
            )
        return tuple(findings)
