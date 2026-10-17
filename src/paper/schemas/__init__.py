"""External PAPER contracts consumed by the reusable extraction boundary."""

from .catalog import PAPER_SCHEMA_NAMES, get_paper_schema
from .installment_schedule import InstallmentSchedule
from .rent_agreement import RentAgreementSchema
from .rent_installment import RentInstallment
from .rent_invoice import RentInvoiceSchema
from .supporting_document import SupportingDocumentSchema
from .tax_invoice import TaxInvoiceSchema
from .utility_statement import UtilityStatementSchema
from .withholding_policy import WithholdingPolicy

__all__ = [
    "PAPER_SCHEMA_NAMES",
    "InstallmentSchedule",
    "RentAgreementSchema",
    "RentInstallment",
    "RentInvoiceSchema",
    "SupportingDocumentSchema",
    "TaxInvoiceSchema",
    "UtilityStatementSchema",
    "WithholdingPolicy",
    "get_paper_schema",
]
