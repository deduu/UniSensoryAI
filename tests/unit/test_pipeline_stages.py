"""Tests for src/pipeline/stages/ — concrete stage implementations."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
from PIL import Image

from src.pipeline.stages.ingestion_stage import IngestionStage
from src.pipeline.stages.conversion_stage import ConversionStage
from src.pipeline.stages.inference_stage import InferenceStage
from src.pipeline.stages.formatting_stage import FormattingStage


# ---------------------------------------------------------------------------
# IngestionStage
# ---------------------------------------------------------------------------


class TestIngestionStage:
    def test_validate_input_requires_file_path(self):
        """validate_input should return False when file_path is missing."""
        stage = IngestionStage()
        assert stage.validate_input({}) is False
        assert stage.validate_input({"file_path": None}) is False

    def test_validate_input_accepts_file_path(self, tmp_path):
        """validate_input should return True when file_path is present."""
        stage = IngestionStage()
        assert stage.validate_input({"file_path": str(tmp_path / "f.pdf")}) is True

    @pytest.mark.asyncio
    async def test_detects_pdf_type(self, tmp_path):
        """PDF files should produce document_type='pdf'."""
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4")

        stage = IngestionStage()
        result = await stage.execute({"file_path": pdf})
        assert result["document_type"] == "pdf"

    @pytest.mark.asyncio
    async def test_detects_image_type(self, tmp_path):
        """Image files should produce document_type='image'."""
        img = tmp_path / "photo.png"
        img.write_bytes(b"fake png")

        stage = IngestionStage()
        result = await stage.execute({"file_path": img})
        assert result["document_type"] == "image"

    @pytest.mark.asyncio
    async def test_detects_excel_type(self, tmp_path):
        """XLSX files should produce document_type='excel'."""
        xlsx = tmp_path / "data.xlsx"
        xlsx.write_bytes(b"fake xlsx")

        stage = IngestionStage()
        result = await stage.execute({"file_path": xlsx})
        assert result["document_type"] == "excel"

    @pytest.mark.asyncio
    async def test_detects_word_type(self, tmp_path):
        """DOCX files should produce document_type='word'."""
        docx = tmp_path / "doc.docx"
        docx.write_bytes(b"fake docx")

        stage = IngestionStage()
        result = await stage.execute({"file_path": docx})
        assert result["document_type"] == "word"

    @pytest.mark.asyncio
    async def test_detects_powerpoint_type(self, tmp_path):
        """PPTX files should produce document_type='powerpoint'."""
        pptx = tmp_path / "slides.pptx"
        pptx.write_bytes(b"fake pptx")

        stage = IngestionStage()
        result = await stage.execute({"file_path": pptx})
        assert result["document_type"] == "powerpoint"

    @pytest.mark.asyncio
    async def test_raises_on_missing_file(self, tmp_path):
        """Non-existent file should raise FileNotFoundError."""
        stage = IngestionStage()
        with pytest.raises(FileNotFoundError):
            await stage.execute({"file_path": tmp_path / "missing.pdf"})

    @pytest.mark.asyncio
    async def test_raises_on_unsupported_extension(self, tmp_path):
        """Unknown extension should raise ValueError."""
        bad = tmp_path / "file.xyz"
        bad.write_bytes(b"content")

        stage = IngestionStage()
        with pytest.raises(ValueError, match="Unsupported"):
            await stage.execute({"file_path": bad})


# ---------------------------------------------------------------------------
# ConversionStage
# ---------------------------------------------------------------------------


class TestConversionStage:
    def test_validate_input_requires_file_path(self):
        """validate_input should return False when file_path is missing."""
        stage = ConversionStage()
        assert stage.validate_input({}) is False

    @pytest.mark.asyncio
    async def test_calls_converter(self, sample_image):
        """ConversionStage should call DocumentConverter.convert."""
        stage = ConversionStage()
        result = await stage.execute({"file_path": sample_image})
        assert "content_items" in result
        assert len(result["content_items"]) >= 1

    @pytest.mark.asyncio
    async def test_passes_page_range(self, sample_pdf):
        """Page range parameters should be forwarded to converter."""
        with patch(
            "src.pipeline.stages.conversion_stage.DocumentConverter.convert",
            return_value=[MagicMock()],
        ) as mock_convert:
            stage = ConversionStage()
            await stage.execute(
                {"file_path": sample_pdf, "start_page": 1, "end_page": 1}
            )
            mock_convert.assert_called_once_with(
                sample_pdf, start_page=1, end_page=1
            )

    @pytest.mark.asyncio
    async def test_raises_on_empty_content(self, tmp_path):
        """Empty conversion result should raise ValueError."""
        with patch(
            "src.pipeline.stages.conversion_stage.DocumentConverter.convert",
            return_value=[],
        ):
            stage = ConversionStage()
            with pytest.raises(ValueError, match="No processable"):
                await stage.execute({"file_path": tmp_path / "empty.pdf"})


# ---------------------------------------------------------------------------
# InferenceStage
# ---------------------------------------------------------------------------


class TestInferenceStage:
    def test_validate_input_requires_content_items_and_model(self):
        """validate_input needs content_items and model_id."""
        stage = InferenceStage()
        assert stage.validate_input({}) is False
        assert stage.validate_input({"content_items": [], "model_id": "x"}) is False
        assert (
            stage.validate_input({"content_items": ["text"], "model_id": "x"}) is True
        )

    @pytest.mark.asyncio
    async def test_processes_text_items(self):
        """Text items should be preserved instead of summarized by the model."""
        mock_model = MagicMock()
        mock_model.process.return_value = {"content": "analyzed"}

        with patch(
            "src.ingestion.processor.get_cached_model",
            new_callable=AsyncMock,
            return_value=mock_model,
        ):
            stage = InferenceStage()
            result = await stage.execute(
                {
                    "model_id": "test-model",
                    "content_items": ["Hello world"],
                    "api_keys": None,
                }
            )

        assert result["raw_results"] == ["Hello world"]
        mock_model.process.assert_not_called()

    @pytest.mark.asyncio
    async def test_processes_image_items(self):
        """Image items should call model.process with image bytes."""
        mock_model = MagicMock()
        mock_model.process.return_value = {"content": "image_result"}
        pil_image = Image.new("RGB", (10, 10), "red")

        with patch(
            "src.ingestion.processor.get_cached_model",
            new_callable=AsyncMock,
            return_value=mock_model,
        ):
            stage = InferenceStage()
            result = await stage.execute(
                {
                    "model_id": "test-model",
                    "content_items": [pil_image],
                    "api_keys": None,
                }
            )

        assert result["raw_results"] == ["image_result"]
        call_kwargs = mock_model.process.call_args
        assert call_kwargs.kwargs.get("image") is not None
        prompt = call_kwargs.kwargs.get("prompt", "")
        assert "faithful Markdown" in prompt
        assert "Do not summarize" in prompt

    @pytest.mark.asyncio
    async def test_uses_cached_model(self):
        """Should call get_cached_model with correct model_id."""
        mock_model = MagicMock()
        mock_model.process.return_value = {"content": "ok"}

        with patch(
            "src.ingestion.processor.get_cached_model",
            new_callable=AsyncMock,
            return_value=mock_model,
        ) as mock_get:
            stage = InferenceStage()
            await stage.execute(
                {
                    "model_id": "gpt-4o",
                    "content_items": ["text"],
                    "api_keys": {"OPENAI_API_KEY": "sk-test"},
                }
            )

        mock_get.assert_called_once_with("gpt-4o", {"OPENAI_API_KEY": "sk-test"})


# ---------------------------------------------------------------------------
# FormattingStage
# ---------------------------------------------------------------------------


class TestFormattingStage:
    def test_validate_input_requires_raw_results(self):
        """validate_input needs non-empty raw_results."""
        stage = FormattingStage()
        assert stage.validate_input({}) is False
        assert stage.validate_input({"raw_results": []}) is False
        assert stage.validate_input({"raw_results": ["text"]}) is True

    @pytest.mark.asyncio
    async def test_aggregates_results(self):
        """Should join results with item separator."""
        stage = FormattingStage()
        result = await stage.execute(
            {
                "raw_results": ["Page 1 content", "Page 2 content"],
                "content_items": ["a", "b"],
            }
        )

        output = result["formatted_output"]
        assert "Page 1 content" in output["content"]
        assert "Page 2 content" in output["content"]
        assert "--- ITEM BREAK ---" in output["content"]
        assert output["page_count"] == 2

    @pytest.mark.asyncio
    async def test_single_result(self):
        """Single result should not have separator."""
        stage = FormattingStage()
        result = await stage.execute(
            {
                "raw_results": ["Only page"],
                "content_items": ["a"],
            }
        )

        output = result["formatted_output"]
        assert output["content"] == "Only page"
        assert "ITEM BREAK" not in output["content"]
        assert output["page_count"] == 1
