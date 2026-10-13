"""Resource ownership and safe failure contracts for the extraction facade."""

from unittest.mock import AsyncMock

import pytest
from pydantic import BaseModel, Field

from src.extraction.contracts import ExternalSchema, ExtractionOptions, PdfSource
from src.extraction.errors import ExtractionError
from src.extraction.schema_validation import SchemaValidationService
from src.extraction.service import ExtractionService


@pytest.mark.asyncio
async def test_close_releases_every_owned_provider_even_when_one_fails() -> None:
    first, second = AsyncMock(), AsyncMock()
    first.aclose.side_effect = RuntimeError("private-credential")
    service = ExtractionService(
        reader=AsyncMock(), gateway=AsyncMock(), owned_providers=(first, second)
    )
    with pytest.raises(ExtractionError) as error:
        await service.aclose()
    assert "private-credential" not in str(error.value)
    assert error.value.__suppress_context__
    second.aclose.assert_awaited_once()
    await service.aclose()
    first.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_closed_service_rejects_work_before_reading_source() -> None:
    reader = AsyncMock()
    service = ExtractionService(reader=reader, gateway=AsyncMock())
    await service.aclose()
    with pytest.raises(ExtractionError, match="closed"):
        await service.extract_document(
            PdfSource(data=b"%PDF-1.7"), ExtractionOptions(text_strategy="native_only")
        )
    reader.read.assert_not_awaited()


def test_schema_failure_hides_sensitive_chained_traceback() -> None:
    schema = ExternalSchema(
        json_schema={"type": "object", "properties": {"total": {"type": "number"}}}
    )
    with pytest.raises(ExtractionError) as error:
        SchemaValidationService.validate({"total": "private-document-value"}, schema)
    assert error.value.__suppress_context__
    assert error.value.__cause__ is None


def test_pydantic_business_aliases_preserve_external_schema_keys() -> None:
    class Invoice(BaseModel):
        invoice_number: str = Field(alias="invoiceNumber")

    schema = ExternalSchema.from_pydantic(Invoice)
    result = SchemaValidationService.validate({"invoiceNumber": "INV-123"}, schema, Invoice)
    assert result == {"invoiceNumber": "INV-123"}
