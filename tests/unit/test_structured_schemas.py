"""Tests for src/structured/schemas.py and registry.py."""

import pytest
from pydantic import ValidationError

from src.structured import (
    FormSchema,
    GenericReportSchema,
    InvoiceLineItem,
    InvoiceSchema,
    ReceiptSchema,
    SchemaRegistry,
)


class TestInvoiceSchema:
    def test_minimal_valid_invoice(self):
        inv = InvoiceSchema(
            vendor_name="Acme",
            invoice_number="INV-1",
            total=12.50,
        )
        assert inv.vendor_name == "Acme"
        assert inv.line_items == []

    def test_rejects_missing_total(self):
        with pytest.raises(ValidationError):
            InvoiceSchema(vendor_name="Acme", invoice_number="INV-1")

    def test_rejects_unknown_field(self):
        with pytest.raises(ValidationError) as exc_info:
            InvoiceSchema(
                vendor_name="A",
                invoice_number="I",
                total=1,
                hallucinated_field="oops",
            )
        assert "extra" in str(exc_info.value).lower() or "forbid" in str(exc_info.value).lower()

    def test_line_items_coerce_strings(self):
        inv = InvoiceSchema(
            vendor_name="A",
            invoice_number="I",
            total=10,
            line_items=[
                {"description": "Widget", "quantity": "2", "unit_price": "5.00", "line_total": "10.00"}
            ],
        )
        assert inv.line_items[0].quantity == 2
        assert inv.line_items[0].line_total == 10.0

    def test_rejects_empty_vendor(self):
        with pytest.raises(ValidationError):
            InvoiceSchema(vendor_name="", invoice_number="I", total=1)


class TestReceiptSchema:
    def test_minimal_valid(self):
        rec = ReceiptSchema(merchant="Coffee Co", total=4.25)
        assert rec.merchant == "Coffee Co"

    def test_strips_whitespace(self):
        rec = ReceiptSchema(merchant="  Coffee Co  ", total=4.25)
        assert rec.merchant == "Coffee Co"


class TestFormSchema:
    def test_empty_fields_allowed(self):
        form = FormSchema()
        assert form.fields == []

    def test_checked_field(self):
        form = FormSchema(fields=[{"label": "Agree", "checked": True}])
        assert form.fields[0].checked is True


class TestGenericReportSchema:
    def test_section_requires_heading_and_content(self):
        with pytest.raises(ValidationError):
            GenericReportSchema(sections=[{"heading": "Intro"}])
        with pytest.raises(ValidationError):
            GenericReportSchema(sections=[{"content": "body"}])

    def test_valid_report(self):
        report = GenericReportSchema(
            title="Q4",
            sections=[{"heading": "Intro", "content": "Body text."}],
        )
        assert len(report.sections) == 1


class TestSchemaRegistry:
    def test_known_subtypes_resolve(self):
        reg = SchemaRegistry()
        assert reg.get("invoice") is InvoiceSchema
        assert reg.get("receipt") is ReceiptSchema
        assert reg.get("form") is FormSchema
        assert reg.get("report") is GenericReportSchema

    def test_unknown_falls_back_to_default(self):
        reg = SchemaRegistry()
        assert reg.get("alien") is GenericReportSchema

    def test_none_falls_back_to_default(self):
        reg = SchemaRegistry()
        assert reg.get(None) is GenericReportSchema

    def test_can_disable_default(self):
        reg = SchemaRegistry(default=None)
        assert reg.get("alien") is None

    def test_register_overrides(self):
        reg = SchemaRegistry()
        reg.register("invoice", FormSchema)
        assert reg.get("invoice") is FormSchema

    def test_known_subtypes_list(self):
        reg = SchemaRegistry()
        assert set(reg.known_subtypes) == {"invoice", "receipt", "form", "report"}
