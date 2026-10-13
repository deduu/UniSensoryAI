"""Real PDF to external business schema through the public embedding facade."""

import json
import subprocess
import sys
from pathlib import Path

import pymupdf
import pytest
from pydantic import BaseModel

from src.extraction import ExtractionOptions, PdfSource, build_extraction_service
from src.extraction.contracts import ModelDescriptor, ModelRequest, ModelResponse
from src.extraction.ports import BaseGenerationProvider


class HostInvoice(BaseModel):
    """This business model belongs to the embedding application."""

    invoice_number: str
    total: int


class HostProvider(BaseGenerationProvider):
    def __init__(self) -> None:
        self.requests: list[ModelRequest] = []
        self.closed = False

    @property
    def descriptor(self) -> ModelDescriptor:
        return ModelDescriptor(
            model_id="external-host", supports_images=True, supports_native_json=True
        )

    async def complete(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        blocks = json.loads(request.prompt.split("Source blocks:\n", 1)[1])
        source_id = blocks[0]["source_id"]
        return ModelResponse(
            model_id="external-host",
            content=json.dumps(
                {
                    "data": {"invoice_number": "INV-123", "total": 120},
                    "evidence": [
                        {
                            "field_path": "/invoice_number",
                            "source_ids": [source_id],
                            "quote": "INV-123",
                        },
                        {"field_path": "/total", "source_ids": [source_id], "quote": "120"},
                    ],
                }
            ),
        )

    async def aclose(self) -> None:
        self.closed = True


def invoice_pdf() -> bytes:
    with pymupdf.open() as pdf:
        page = pdf.new_page(width=250, height=250)
        page.insert_text((20, 30), "Invoice INV-123\nTotal 120")
        return pdf.tobytes()


@pytest.mark.asyncio
async def test_real_pdf_embedding_and_serialization_reuse() -> None:
    provider = HostProvider()
    service = await build_extraction_service(providers={"fields": provider})
    try:
        result = await service.extract(
            PdfSource(data=invoice_pdf(), filename="invoice.pdf"),
            options=ExtractionOptions(content_mode="text", text_strategy="native_only"),
            schema=HostInvoice,
        )
        assert result.document.page_count == 1
        assert result.document.pages[0].images == ()
        assert result.fields.data == {"invoice_number": "INV-123", "total": 120}
        assert result.status == "succeeded"
        reused = await service.extract_fields(result.document.model_dump(), HostInvoice)
        assert reused.data == result.fields.data
        assert not provider.requests[0].images
    finally:
        await service.aclose()
    assert not provider.closed


@pytest.mark.asyncio
async def test_native_multimodal_extraction_needs_no_provider() -> None:
    service = await build_extraction_service()
    try:
        document = await service.extract_document(
            PdfSource(data=invoice_pdf()),
            ExtractionOptions(content_mode="multimodal", text_strategy="native_only"),
        )
        assert "INV-123" in document.text
        assert document.pages[0].images[0].kind == "page"
        assert document.pages[0].images[0].data_base64
    finally:
        await service.aclose()


def test_importing_embedding_api_does_not_load_app_or_ml_stack() -> None:
    script = "import sys; import src.extraction; assert not any(n in sys.modules for n in ('torch', 'transformers', 'src.db.session', 'src.api.server', 'src.models.loader'))"
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=20, check=False
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("mode", ["text", "multimodal"])
def test_cli_stdout_is_a_single_json_result(tmp_path: Path, mode: str) -> None:
    source = tmp_path / "invoice.pdf"
    source.write_bytes(invoice_pdf())
    result = subprocess.run(
        [sys.executable, "-m", "examples.extract_pdf", str(source), "--mode", mode],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["document"]["page_count"] == 1
    assert bool(payload["document"]["pages"][0]["images"]) == (mode == "multimodal")
