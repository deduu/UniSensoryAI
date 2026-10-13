"""Boundary validation for reusable extraction, independent of model SDKs."""

from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError

from src.extraction.contracts import ExternalSchema, ExtractionOptions, FieldEvidence, PdfSource


def test_source_requires_exactly_one_input(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        PdfSource()
    with pytest.raises(ValidationError):
        PdfSource(path=tmp_path / "file.pdf", data=b"%PDF-1.7")
    assert PdfSource(data=b"%PDF-1.7").filename == "document.pdf"


def test_options_keep_output_mode_separate_from_ocr_strategy() -> None:
    options = ExtractionOptions(content_mode="text", text_strategy="native_then_ocr")
    assert options.content_mode == "text"
    assert options.text_strategy == "native_then_ocr"
    with pytest.raises(ValidationError):
        ExtractionOptions(start_page=4, end_page=2)
    with pytest.raises(ValidationError):
        ExtractionOptions(content_mode="summary")


def test_external_schema_validates_schema_and_rejects_remote_references() -> None:
    schema = ExternalSchema(
        schema_id="po", json_schema={"type": "object", "properties": {"po": {"type": "string"}}}
    )
    assert schema.schema_id == "po"
    with pytest.raises(ValidationError):
        ExternalSchema(json_schema={"type": "not-a-type"})
    with pytest.raises(ValidationError):
        ExternalSchema(json_schema={"type": "object", "$ref": "https://example.com/schema"})


def test_pydantic_schemas_are_external_and_keep_local_definitions() -> None:
    class Line(BaseModel):
        sku: str

    class PurchaseOrder(BaseModel):
        po_number: str
        lines: list[Line]

    schema = ExternalSchema.from_pydantic(PurchaseOrder)
    assert schema.schema_id == "PurchaseOrder"
    assert schema.json_schema["$defs"]


def test_evidence_cannot_use_an_empty_quote() -> None:
    with pytest.raises(ValidationError):
        FieldEvidence(field_path="/po", source_ids=("p1-text",), quote=" \n\t")
