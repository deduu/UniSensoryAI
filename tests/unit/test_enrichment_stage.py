"""Tests for src/pipeline/stages/enrichment_stage.py and the chunked formatting output."""

import sys
from unittest.mock import MagicMock

import pytest

_MOCK_MODULES = [
    "fitz",
    "torch", "torch.cuda", "torch.nn", "torch.nn.functional",
    "torchvision", "torchvision.transforms",
    "transformers", "accelerate", "bitsandbytes",
]
for _mod in _MOCK_MODULES:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

from src.ingestion.pdf_hybrid import PageBundle
from src.pipeline.stages.enrichment_stage import EnrichmentStage
from src.pipeline.stages.formatting_stage import FormattingStage


def _bundle(page_no: int, text: str = "") -> PageBundle:
    return PageBundle(
        page_no=page_no,
        text_layer=text,
        image_regions=[],
        full_page_image=None,
        needs_full_page_vlm=False,
    )


class TestEnrichmentStage:
    @pytest.mark.asyncio
    async def test_minimal_only_raw_results(self):
        stage = EnrichmentStage()
        ctx = {"raw_results": ["page one body", "page two body"]}
        result = await stage.execute(ctx)
        chunks = result["content_chunks"]
        assert len(chunks) == 2
        assert chunks[0] == {"page": 1, "type": "page", "content": "page one body"}
        assert chunks[1]["page"] == 2

    @pytest.mark.asyncio
    async def test_uses_pagebundle_page_no(self):
        """When PageBundles are present, ``page`` reflects the bundle, not the index."""
        stage = EnrichmentStage()
        ctx = {
            "raw_results": ["a", "b"],
            "page_bundles": [_bundle(7), _bundle(8)],
        }
        result = await stage.execute(ctx)
        chunks = result["content_chunks"]
        assert chunks[0]["page"] == 7
        assert chunks[1]["page"] == 8

    @pytest.mark.asyncio
    async def test_appends_structured_chunks(self):
        stage = EnrichmentStage()
        ctx = {
            "raw_results": ["a"],
            "structured_chunks": [
                {"schema_id": "invoice", "content": {"vendor_name": "Acme", "total": 1}}
            ],
        }
        result = await stage.execute(ctx)
        chunks = result["content_chunks"]
        assert chunks[1] == {
            "page": None,
            "type": "structured",
            "schema_id": "invoice",
            "content": {"vendor_name": "Acme", "total": 1},
        }

    @pytest.mark.asyncio
    async def test_surfaces_content_validation_notes(self):
        stage = EnrichmentStage()
        ctx = {
            "raw_results": ["a"],
            "validation_errors": [
                {"stage": "content_validation", "page": 1, "notes": "MISSING: x"},
                {"stage": "structured_output", "schema_id": "invoice", "error": "..."},
            ],
        }
        result = await stage.execute(ctx)
        # Only content_validation errors become chunks. structured_output
        # failures live in validation_errors only.
        validation_chunks = [c for c in result["content_chunks"] if c["type"] == "validation"]
        assert len(validation_chunks) == 1
        assert validation_chunks[0]["page"] == 1
        assert validation_chunks[0]["content"]["notes"] == "MISSING: x"


class TestFormattingChunks:
    @pytest.mark.asyncio
    async def test_uses_enrichment_chunks_when_present(self):
        formatting = FormattingStage()
        custom_chunks = [{"page": 1, "type": "page", "content": "x"}]
        ctx = {
            "raw_results": ["x"],
            "content_items": ["x"],
            "content_chunks": custom_chunks,
        }
        result = await formatting.execute(ctx)
        assert result["formatted_output"]["chunks"] is custom_chunks

    @pytest.mark.asyncio
    async def test_fallback_chunks_when_enrichment_absent(self):
        """Basic pipeline (no enrichment) still produces per-page chunks."""
        formatting = FormattingStage()
        ctx = {
            "raw_results": ["one", "two"],
            "content_items": [object(), object()],
        }
        result = await formatting.execute(ctx)
        chunks = result["formatted_output"]["chunks"]
        assert len(chunks) == 2
        assert chunks[0] == {"page": 1, "type": "page", "content": "one"}

    @pytest.mark.asyncio
    async def test_passes_validation_errors_through(self):
        formatting = FormattingStage()
        errs = [{"stage": "content_validation", "page": 1, "notes": "..."}]
        ctx = {
            "raw_results": ["x"],
            "content_items": ["x"],
            "validation_errors": errs,
        }
        result = await formatting.execute(ctx)
        assert result["formatted_output"]["validation_errors"] == errs
