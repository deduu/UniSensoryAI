"""Tests for src/ingestion/processor.py — model_id threading and processing logic.

Since processor.py now delegates to PipelineExecutor, these tests patch at
the stage-level dependencies (DocumentConverter in conversion_stage,
get_cached_model in processor module) to verify end-to-end behavior through
the pipeline.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from PIL import Image


@pytest.mark.asyncio
async def test_process_document_job_uses_provided_model_id(tmp_path):
    """Passing model_id should forward it to get_cached_model, not use hardcoded default."""
    img_path = tmp_path / "test.png"
    Image.new("RGB", (10, 10), "red").save(img_path)

    mock_model = MagicMock()
    mock_model.process.return_value = {"content": "result"}

    with (
        patch(
            "src.pipeline.stages.conversion_stage.DocumentConverter.convert_hybrid",
            return_value=["text content"],
        ),
        patch(
            "src.ingestion.processor.get_cached_model",
            new_callable=AsyncMock,
            return_value=mock_model,
        ) as mock_get_model,
    ):
        from src.ingestion.processor import process_document_job

        await process_document_job(str(img_path), model_id="gpt-4o")
        mock_get_model.assert_called_once_with("gpt-4o", None)


@pytest.mark.asyncio
async def test_process_document_job_defaults_model_id(tmp_path):
    """Omitting model_id should default to 'qwen2-vl-2b-instruct'."""
    img_path = tmp_path / "test.png"
    Image.new("RGB", (10, 10), "red").save(img_path)

    mock_model = MagicMock()
    mock_model.process.return_value = {"content": "result"}

    with (
        patch(
            "src.pipeline.stages.conversion_stage.DocumentConverter.convert_hybrid",
            return_value=["text content"],
        ),
        patch(
            "src.ingestion.processor.get_cached_model",
            new_callable=AsyncMock,
            return_value=mock_model,
        ) as mock_get_model,
    ):
        from src.ingestion.processor import process_document_job

        await process_document_job(str(img_path))
        mock_get_model.assert_called_once_with("qwen2-vl-2b-instruct", None)


@pytest.mark.asyncio
async def test_process_document_job_text_processing(tmp_path):
    """Text content items should be preserved as full extracted text."""
    txt_path = tmp_path / "test.docx"
    txt_path.touch()

    mock_model = MagicMock()
    mock_model.process.return_value = {"content": "analyzed text"}

    with (
        patch(
            "src.pipeline.stages.conversion_stage.DocumentConverter.convert_hybrid",
            return_value=["Sheet content here"],
        ),
        patch(
            "src.ingestion.processor.get_cached_model",
            new_callable=AsyncMock,
            return_value=mock_model,
        ),
    ):
        from src.ingestion.processor import process_document_job

        result = await process_document_job(str(txt_path), model_id="qwen2-vl-2b-instruct")

        assert result["content"] == "Sheet content here"
        mock_model.process.assert_not_called()


@pytest.mark.asyncio
async def test_process_document_job_image_processing(tmp_path):
    """Image content items should be sent as bytes to model.process."""
    img_path = tmp_path / "test.png"
    Image.new("RGB", (10, 10), "blue").save(img_path)

    pil_image = Image.new("RGB", (10, 10), "blue")

    mock_model = MagicMock()
    mock_model.process.return_value = {"content": "image analysis"}

    with (
        patch(
            "src.pipeline.stages.conversion_stage.DocumentConverter.convert_hybrid",
            return_value=[pil_image],
        ),
        patch(
            "src.ingestion.processor.get_cached_model",
            new_callable=AsyncMock,
            return_value=mock_model,
        ),
    ):
        from src.ingestion.processor import process_document_job

        result = await process_document_job(str(img_path), model_id="qwen2-vl-2b-instruct")

        assert "content" in result
        # model.process should have been called with image bytes
        call_kwargs = mock_model.process.call_args
        assert call_kwargs.kwargs.get("image") is not None


@pytest.mark.asyncio
async def test_process_document_job_file_not_found():
    """Non-existent file should raise FileNotFoundError."""
    from src.ingestion.processor import process_document_job

    with pytest.raises(FileNotFoundError):
        await process_document_job("/nonexistent/path/file.pdf", model_id="qwen2-vl-2b-instruct")


@pytest.mark.asyncio
async def test_process_document_job_conversion_failure(tmp_path):
    """Converter failure should return error dict."""
    fake_path = tmp_path / "bad.pdf"
    fake_path.touch()

    with patch(
        "src.pipeline.stages.conversion_stage.DocumentConverter.convert_hybrid",
        side_effect=RuntimeError("conversion error"),
    ):
        from src.ingestion.processor import process_document_job

        result = await process_document_job(str(fake_path), model_id="qwen2-vl-2b-instruct")
        assert "error" in result
        assert "conversion" in result["error"].lower()
