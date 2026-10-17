"""Portable PAPER extraction contracts stay separate from approved business data."""

import json
import subprocess
import sys
from datetime import date

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError as SchemaValidationError
from pydantic import BaseModel, Field, ValidationError

from src.extraction.contracts import ExternalSchema
from src.extraction.schema_validation import SchemaValidationService
from src.paper.schemas import (
    PAPER_SCHEMA_NAMES,
    RentAgreementSchema,
    RentInvoiceSchema,
    SupportingDocumentSchema,
    TaxInvoiceSchema,
    UtilityStatementSchema,
    get_paper_schema,
)


def test_catalog_discovery_lists_all_five_supported_names() -> None:
    assert PAPER_SCHEMA_NAMES == (
        "rent_agreement",
        "rent_invoice",
        "tax_invoice",
        "utility_statement",
        "supporting_document",
    )


@pytest.mark.parametrize(
    ("name", "model"),
    [
        ("rent_agreement", RentAgreementSchema),
        ("rent_invoice", RentInvoiceSchema),
        ("tax_invoice", TaxInvoiceSchema),
        ("utility_statement", UtilityStatementSchema),
        ("supporting_document", SupportingDocumentSchema),
    ],
)
def test_all_paper_schemas_are_versioned_portable_and_accept_unknown_terms(
    name: str, model: type[BaseModel]
) -> None:
    schema = get_paper_schema(name)
    assert schema.schema_id == f"paper.{name}"
    assert schema.version == "1"
    Draft202012Validator.check_schema(schema.json_schema)
    assert schema.json_schema["additionalProperties"] is False
    normalized = SchemaValidationService.validate({}, schema, model)
    assert normalized["extensions"] == {}
    assert model.model_validate_json(json.dumps(normalized)) == model()


def test_agreement_covers_required_extracted_terms_and_excludes_approved_classification() -> None:
    expected = {
        "vendor_name",
        "vendor_id",
        "store_id",
        "location",
        "contract_number",
        "lease_start_date",
        "lease_end_date",
        "lease_duration_months",
        "payment_schedule",
        "rent_type",
        "currency",
        "fixed_rent",
        "revenue_share_rate",
        "minimum_guaranteed_payment",
        "renewal_terms",
        "other_key_terms",
        "bank_account",
        "extensions",
    }
    assert expected <= RentAgreementSchema.model_fields.keys()
    unknown = RentAgreementSchema().model_dump(mode="json")
    assert unknown["fixed_rent"] is None
    assert unknown["payment_schedule"] is None
    assert unknown["lease_start_date"] is None
    with pytest.raises(ValidationError):
        RentAgreementSchema.model_validate({"psak73_classification": "psak73"})


def test_decimal_strings_dates_and_bank_account_round_trip_without_loss() -> None:
    data = {
        "vendor_name": "Landlord Example",
        "store_id": "STORE-001",
        "contract_number": "RA-1",
        "lease_start_date": "2026-01-01",
        "lease_end_date": "2027-12-31",
        "currency": "IDR",
        "fixed_rent": "9007199254740993.123456789",
        "minimum_guaranteed_payment": "0.00",
        "revenue_share_rate": "0.025",
        "bank_account": "000123456789",
        "extensions": {"cost_center": "CC-8"},
    }
    result = SchemaValidationService.validate(
        data, get_paper_schema("rent_agreement"), RentAgreementSchema
    )
    assert result["fixed_rent"] == data["fixed_rent"]
    assert result["bank_account"] == "000123456789"
    assert result["lease_start_date"] == "2026-01-01"
    assert result["extensions"] == {"cost_center": "CC-8"}


@pytest.mark.parametrize("value", [12, 12.5, True, "NaN", "Infinity", "1e4", "", "1,000.00"])
def test_numeric_or_nonfinite_money_is_rejected_in_models_and_portable_schemas(
    value: object,
) -> None:
    with pytest.raises(ValidationError):
        RentAgreementSchema(fixed_rent=value)
    with pytest.raises(SchemaValidationError):
        Draft202012Validator(get_paper_schema("rent_agreement").json_schema).validate(
            {"fixed_rent": value}
        )


def test_negative_invoice_amount_is_preserved_for_adjustments() -> None:
    invoice = RentInvoiceSchema(total="-100.05")
    assert invoice.model_dump(mode="json")["total"] == "-100.05"


@pytest.mark.parametrize("value", [0, -1, 1.5, True, "12"])
def test_duration_is_a_positive_integer(value: object) -> None:
    with pytest.raises(ValidationError):
        RentAgreementSchema(lease_duration_months=value)


@pytest.mark.parametrize(
    ("model", "start", "end"),
    [
        (RentAgreementSchema, "lease_start_date", "lease_end_date"),
        (RentInvoiceSchema, "service_period_start", "service_period_end"),
        (TaxInvoiceSchema, "service_period_start", "service_period_end"),
        (UtilityStatementSchema, "service_period_start", "service_period_end"),
    ],
)
def test_typed_contracts_reject_reversed_periods_and_allow_partial_dates(
    model: type[BaseModel], start: str, end: str
) -> None:
    with pytest.raises(ValidationError):
        model.model_validate({start: "2026-02-02", end: "2026-02-01"})
    assert model.model_validate({start: "2026-02-02"}).model_dump(mode="json")[end] is None
    assert getattr(model.model_validate({start: "2026-02-02", end: "2026-02-02"}), start) == date(
        2026, 2, 2
    )


def test_portable_contract_validates_calendar_dates() -> None:
    schema = get_paper_schema("rent_agreement")
    with pytest.raises(SchemaValidationError):
        Draft202012Validator(schema.json_schema, format_checker=FormatChecker()).validate(
            {"lease_start_date": "2026-02-30"}
        )


def test_unknown_fields_require_explicit_extensions_or_external_subclass() -> None:
    with pytest.raises(ValidationError):
        RentInvoiceSchema.model_validate({"cost_center": "CC-1"})
    assert RentInvoiceSchema(extensions={"cost_center": "CC-1"}).extensions == {
        "cost_center": "CC-1"
    }

    class HostInvoice(RentInvoiceSchema):
        """Host-owned capability contract extending PAPER terms."""

        cost_center: str = Field(min_length=1)

    exported = ExternalSchema.from_pydantic(HostInvoice, schema_id="host.invoice", version="2")
    result = SchemaValidationService.validate({"cost_center": "CC-1"}, exported, HostInvoice)
    assert result["cost_center"] == "CC-1"


@pytest.mark.parametrize(
    ("name", "version"), [("unknown", "1"), ("rent_agreement", "2"), ("rent_invoice", "")]
)
def test_catalog_rejects_unknown_names_and_versions(name: str, version: str) -> None:
    with pytest.raises(ValueError):
        get_paper_schema(name, version=version)


def test_catalog_returns_fresh_definitions_and_cannot_be_mutated_across_callers() -> None:
    schema = get_paper_schema("rent_agreement")
    schema.json_schema["title"] = "mutated"
    assert get_paper_schema("rent_agreement").json_schema["title"] == "RentAgreementSchema"


@pytest.mark.parametrize("value", ["", "   ", 123])
def test_business_identities_are_nonempty_strings_when_present(value: object) -> None:
    with pytest.raises(ValidationError):
        RentAgreementSchema(contract_number=value)


def test_schema_imports_do_not_load_application_or_model_stack() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import src.paper.schemas; assert not any(name in sys.modules for name in ('torch', 'transformers', 'src.api.server', 'src.db.session', 'src.models.loader'))",
        ],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_agreement_schema_describes_business_roles_address_and_payment_basis() -> None:
    properties = get_paper_schema("rent_agreement").json_schema["properties"]
    assert "landlord" in properties["vendor_name"]["description"].lower()
    assert "notary" in properties["location"]["description"].lower()
    assert "installment" in properties["fixed_rent"]["description"].lower()
    assert "fixed_rent_basis" in properties["fixed_rent"]["description"]
    assert "after" in properties["payment_schedule"]["description"].lower()
    assert "renewal" in properties["lease_duration_months"]["description"].lower()
    assert "fit-out" in properties["lease_start_date"]["description"].lower()


def test_invoice_schema_distinguishes_payable_and_signed_tax_components() -> None:
    properties = get_paper_schema("rent_invoice").json_schema["properties"]
    assert "customer" in properties["vendor_name"]["description"].lower()
    assert "premises" in properties["location"]["description"].lower()
    assert "gross" in properties["subtotal"]["description"].lower()
    assert "withholding" in properties["tax_amount"]["description"].lower()
    assert "vat" in properties["tax_amount"]["description"].lower()
    assert "payable" in properties["total"]["description"].lower()
    assert "invoice date" in properties["service_period_start"]["description"].lower()
    # Guidance annotates the portable schema without adding sample-specific requirements.
    normalized = SchemaValidationService.validate(
        {}, get_paper_schema("rent_invoice"), RentInvoiceSchema
    )
    assert normalized["vendor_id"] is None
    assert normalized["service_period_start"] is None


def test_optional_rent_basis_is_portable_typed_and_keeps_unknown_host_extensions() -> None:
    schema = get_paper_schema("rent_agreement")
    basis = schema.json_schema["properties"]["extensions"]["properties"]["fixed_rent_basis"]
    Draft202012Validator.check_schema(basis)
    for value in ("annual", "monthly", "whole_term", "source-specific unit", None):
        payload = {
            "fixed_rent": "1200",
            "extensions": {
                "fixed_rent_basis": value,
                "host_terms": {"reviewed": False},
            },
        }
        restored = SchemaValidationService.validate(payload, schema, RentAgreementSchema)
        assert restored["extensions"] == payload["extensions"]
    # The v1 contract still accepts drafts created before basis metadata existed.
    assert RentAgreementSchema(fixed_rent="1200").extensions == {}


@pytest.mark.parametrize("value", [123, True, [], {}, "", "   "])
def test_optional_rent_basis_rejects_nontext_or_blank_metadata(value: object) -> None:
    payload = {"extensions": {"fixed_rent_basis": value}}
    with pytest.raises(ValidationError):
        RentAgreementSchema.model_validate(payload)
    with pytest.raises(SchemaValidationError):
        Draft202012Validator(get_paper_schema("rent_agreement").json_schema).validate(payload)
