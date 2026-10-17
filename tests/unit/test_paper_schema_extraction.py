"""Existing extraction consumes PAPER schemas through injected model-neutral ports."""

import json
from unittest.mock import AsyncMock

import pytest

from src.extraction.contracts import (
    DocumentResult,
    ModelDescriptor,
    ModelResponse,
    PageContent,
    TextBlock,
)
from src.extraction.service import ExtractionService
from src.paper.schemas import RentAgreementSchema, get_paper_schema


@pytest.mark.asyncio
async def test_existing_field_extraction_consumes_external_paper_schema() -> None:
    source_text = "Contract RA-2026-042, Store STORE-008, Landlord Example"
    block = TextBlock(block_id="p1-text-1", page_number=1, text=source_text)
    document = DocumentResult(
        document_id="agreement-source-1",
        source_name="agreement.pdf",
        content_mode="text",
        text=source_text,
        pages=(PageContent(page_number=1, width=600, height=800, text_blocks=(block,)),),
    )
    gateway = AsyncMock()
    gateway.describe = lambda profile: ModelDescriptor(model_id="host-model", supports_images=False)
    gateway.generate.return_value = ModelResponse(
        model_id="host-model",
        content=json.dumps(
            {
                "data": {
                    "contract_number": "RA-2026-042",
                    "store_id": "STORE-008",
                    "vendor_name": "Landlord Example",
                },
                "evidence": [
                    {
                        "field_path": "/contract_number",
                        "source_ids": ["p1-text-1"],
                        "quote": "RA-2026-042",
                    },
                    {"field_path": "/store_id", "source_ids": ["p1-text-1"], "quote": "STORE-008"},
                    {
                        "field_path": "/vendor_name",
                        "source_ids": ["p1-text-1"],
                        "quote": "Landlord Example",
                    },
                ],
            }
        ),
    )
    service = ExtractionService(reader=AsyncMock(), gateway=gateway)
    result = await service.extract_fields(
        document, get_paper_schema("rent_agreement"), model_profile="paper.fields"
    )
    assert result.schema_id == "paper.rent_agreement"
    assert result.schema_version == "1"
    assert RentAgreementSchema.model_validate(result.data).contract_number == "RA-2026-042"
    assert result.status == "succeeded"
    assert len(result.evidence) == 3
    assert "paper.fields" == gateway.generate.await_args.args[0]
