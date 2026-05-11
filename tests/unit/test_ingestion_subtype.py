"""Tests for the subtype-detection logic in src/pipeline/stages/ingestion_stage.py."""

import sys
from unittest.mock import MagicMock

import pytest

# Same heavy-deps stubbing pattern as test_inference_parallel.py — the
# pipeline package eagerly imports converter.py (PyMuPDF) and the models
# package (transformers).
_MOCK_MODULES = [
    "fitz",
    "torch", "torch.cuda", "torch.nn", "torch.nn.functional",
    "torchvision", "torchvision.transforms",
    "transformers", "accelerate", "bitsandbytes",
]
for _mod in _MOCK_MODULES:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

from src.pipeline.stages.ingestion_stage import (
    IngestionStage,
    _detect_subtype_from_filename,
)


class TestFilenameHeuristics:
    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("invoice_2026_01_15.pdf", "invoice"),
            ("INV-001.pdf", "invoice"),
            ("acme_bill_january.pdf", "invoice"),
            ("grocery_receipt.png", "receipt"),
            ("rec-7782.jpg", "receipt"),
            ("intake_form.pdf", "form"),
            ("loan_application.docx", "form"),
            ("Q4_report.pdf", "report"),
            ("annual_memo.docx", "report"),
            ("random_document.pdf", None),
            ("scan001.pdf", None),
        ],
    )
    def test_filename_to_subtype(self, name, expected):
        assert _detect_subtype_from_filename(name) == expected


class TestIngestionStageSubtype:
    @pytest.mark.asyncio
    async def test_sets_subtype_from_filename(self, tmp_path):
        pdf = tmp_path / "ACME_invoice_42.pdf"
        pdf.write_bytes(b"%PDF-1.4")

        stage = IngestionStage()
        ctx = {"file_path": pdf}
        result = await stage.execute(ctx)

        assert result["document_type"] == "pdf"
        assert result["document_subtype"] == "invoice"

    @pytest.mark.asyncio
    async def test_no_subtype_for_neutral_name(self, tmp_path):
        pdf = tmp_path / "untitled.pdf"
        pdf.write_bytes(b"%PDF-1.4")

        stage = IngestionStage()
        result = await stage.execute({"file_path": pdf})

        assert result["document_type"] == "pdf"
        assert result["document_subtype"] is None

    @pytest.mark.asyncio
    async def test_does_not_overwrite_caller_subtype(self, tmp_path):
        pdf = tmp_path / "ACME_invoice_42.pdf"
        pdf.write_bytes(b"%PDF-1.4")

        stage = IngestionStage()
        # Caller already supplied a more specific subtype.
        result = await stage.execute(
            {"file_path": pdf, "document_subtype": "custom-form"}
        )

        assert result["document_subtype"] == "custom-form"
