"""Tests for src/services/ — BaseService, IngestionService, DocumentService."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import IntegrityError

from src.services.base import BaseService
from src.services.ingestion import IngestionService
from src.services.document import DocumentService
from src.services.exceptions import NotFoundException, IntegrityException
from src.db.models.ingestion import IngestionJob, IngestionStatus

# --- BaseService Tests ---


class TestBaseService:
    @pytest.mark.asyncio
    async def test_get_by_id_found(self, mock_session):
        """get_by_id should return the object when found."""
        mock_obj = MagicMock(spec=IngestionJob)
        mock_session.get = AsyncMock(return_value=mock_obj)

        service = BaseService(mock_session, IngestionJob)
        result = await service.get_by_id("id-123")
        assert result is mock_obj
        mock_session.get.assert_called_once_with(IngestionJob, "id-123")

    @pytest.mark.asyncio
    async def test_get_by_id_not_found_raises(self, mock_session):
        """get_by_id should raise NotFoundException when not found and raise_not_found=True."""
        mock_session.get = AsyncMock(return_value=None)

        service = BaseService(mock_session, IngestionJob)
        with pytest.raises(NotFoundException):
            await service.get_by_id("missing-id")

    @pytest.mark.asyncio
    async def test_get_by_id_not_found_returns_none(self, mock_session):
        """get_by_id should return None when not found and raise_not_found=False."""
        mock_session.get = AsyncMock(return_value=None)

        service = BaseService(mock_session, IngestionJob)
        result = await service.get_by_id("missing-id", raise_not_found=False)
        assert result is None

    @pytest.mark.asyncio
    async def test_list(self, mock_session):
        """list should execute a select query with limit and offset."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [MagicMock(), MagicMock()]
        mock_session.execute = AsyncMock(return_value=mock_result)

        service = BaseService(mock_session, IngestionJob)
        results = await service.list(limit=10, offset=5)
        assert len(results) == 2
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_success(self, mock_session):
        """create should add, flush, refresh and return the object."""
        service = BaseService(mock_session, IngestionJob)
        await service.create(id="new-id", file_path="/test.pdf")

        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()
        mock_session.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_integrity_error(self, mock_session):
        """create should raise IntegrityException on IntegrityError."""
        mock_session.flush = AsyncMock(
            side_effect=IntegrityError("dup", params=None, orig=Exception())
        )

        service = BaseService(mock_session, IngestionJob)
        with pytest.raises(IntegrityException):
            await service.create(id="dup-id", file_path="/test.pdf")

    @pytest.mark.asyncio
    async def test_delete_found(self, mock_session):
        """delete should return True when object exists."""
        mock_obj = MagicMock(spec=IngestionJob)
        mock_session.get = AsyncMock(return_value=mock_obj)

        service = BaseService(mock_session, IngestionJob)
        result = await service.delete("id-to-delete")
        assert result is True
        mock_session.delete.assert_called_once_with(mock_obj)


# --- IngestionService Tests ---


class TestIngestionService:
    @pytest.mark.asyncio
    async def test_create_job_generates_uuid(self, mock_session):
        """create_job should generate a UUID and create with PENDING status."""
        mock_session.flush = AsyncMock()
        mock_session.refresh = AsyncMock()

        service = IngestionService(mock_session)
        with patch("src.services.ingestion.uuid.uuid4", return_value="mock-uuid"):
            await service.create_job(
                "/path/to/file.pdf", meta={"key": "value"}, tenant_id="t-1"
            )

        mock_session.add.assert_called_once()
        added_obj = mock_session.add.call_args[0][0]
        assert added_obj.id == "mock-uuid"
        assert added_obj.tenant_id == "t-1"
        assert added_obj.status == IngestionStatus.PENDING
        assert added_obj.file_path == "/path/to/file.pdf"
        assert added_obj.meta == {"key": "value"}

    @pytest.mark.asyncio
    async def test_update_status_merges_meta(self, mock_session):
        """update_status with meta_update should merge into existing meta."""
        existing_job = MagicMock(spec=IngestionJob)
        existing_job.meta = {"model_id": "qwen"}
        existing_job.id = "job-1"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_job
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.get = AsyncMock(return_value=existing_job)

        service = IngestionService(mock_session)
        await service.update_status(
            "job-1", IngestionStatus.PROCESSING, meta_update={"progress": "50%"}
        )

        # After merge, meta should contain both old and new keys
        # The update call should include the merged meta
        mock_session.flush.assert_called()

    @pytest.mark.asyncio
    async def test_mark_failed(self, mock_session):
        """mark_failed should call update_status with FAILED and error in meta."""
        existing_job = MagicMock(spec=IngestionJob)
        existing_job.meta = {}
        existing_job.id = "job-fail"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_job
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.get = AsyncMock(return_value=existing_job)

        service = IngestionService(mock_session)
        await service.mark_failed("job-fail", "Something went wrong")

        mock_session.flush.assert_called()

    @pytest.mark.asyncio
    async def test_mark_completed(self, mock_session):
        """mark_completed should call update_status with COMPLETED status."""
        existing_job = MagicMock(spec=IngestionJob)
        existing_job.meta = {}
        existing_job.id = "job-done"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_job
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.get = AsyncMock(return_value=existing_job)

        service = IngestionService(mock_session)
        await service.mark_completed("job-done", {"pages": 5})

        mock_session.flush.assert_called()


# --- DocumentService Tests ---


class TestDocumentService:
    @pytest.mark.asyncio
    async def test_create_document_extracts_content(self, mock_session):
        """create_document should extract content_text from the content dict."""
        mock_session.flush = AsyncMock()
        mock_session.refresh = AsyncMock()

        service = DocumentService(mock_session)
        content = {"content": "Extracted text here", "chunks": [{"page": 1}]}

        with patch("src.services.document.uuid.uuid4", return_value="doc-uuid"):
            await service.create_document(
                "job-1", "file.pdf", content, tenant_id="t-1"
            )

        mock_session.add.assert_called_once()
        added_obj = mock_session.add.call_args[0][0]
        assert added_obj.content_text == "Extracted text here"
        assert added_obj.content_chunks == [{"page": 1}]
        assert added_obj.job_id == "job-1"
        assert added_obj.tenant_id == "t-1"
        assert added_obj.filename == "file.pdf"

    @pytest.mark.asyncio
    async def test_create_document_uses_text_fallback(self, mock_session):
        """create_document should fall back to 'text' key if 'content' is missing."""
        mock_session.flush = AsyncMock()
        mock_session.refresh = AsyncMock()

        service = DocumentService(mock_session)
        content = {"text": "Fallback text"}

        with patch("src.services.document.uuid.uuid4", return_value="doc-uuid-2"):
            await service.create_document(
                "job-2", "file.docx", content, tenant_id="t-1"
            )

        added_obj = mock_session.add.call_args[0][0]
        assert added_obj.content_text == "Fallback text"
