import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from src.ingestion.queue_manager import IngestionQueue, RateLimiter
from src.db.models.ingestion import IngestionJob, IngestionStatus

@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.commit = AsyncMock()
    return session

@pytest.fixture
def mock_session_manager(mock_session):
    manager = MagicMock()
    manager.session.return_value.__aenter__.return_value = mock_session
    return manager

@pytest.mark.asyncio
async def test_ingestion_queue_flow():
    # Mock DB interaction
    with patch("src.ingestion.queue_manager.session_manager") as mock_manager:
        mock_session = AsyncMock()
        mock_manager.session.return_value.__aenter__.return_value = mock_session
        
        # Mock IngestionService within the queue manager's usage
        with patch("src.ingestion.queue_manager.IngestionService") as MockServiceArg:
            mock_service_instance = MockServiceArg.return_value
            
            # Setup mock return values
            mock_job = MagicMock(spec=IngestionJob)
            mock_job.id = "test-job-id"
            mock_job.file_path = "test.pdf"
            
            # Helper to create proper async mocks
            mock_service_instance.create_job = AsyncMock(return_value=mock_job)
            mock_service_instance.update_status = AsyncMock(return_value=mock_job)
            # mark_completed returns IngestionJob too
            mock_service_instance.mark_completed = AsyncMock(return_value=mock_job)
            
            # Processing function
            async def dummy_processor(file_path):
                await asyncio.sleep(0.01)
                return "processed"
                
            queue = IngestionQueue(dummy_processor)
            
            # 1. Enqueue
            job_id = await queue.enqueue("test.pdf")
            assert job_id == "test-job-id"
            mock_service_instance.create_job.assert_called_once()
            
            # 2. Start Worker
            await queue.start_worker()
            
            # Allow worker to pick up item
            await asyncio.sleep(0.1)
            
            # Verify processing happened
            mock_service_instance.update_status.assert_any_call("test-job-id", IngestionStatus.PROCESSING)
            mock_service_instance.mark_completed.assert_called_with("test-job-id", {'result': 'processed'})
            
            await queue.stop_worker()

@pytest.mark.asyncio
async def test_ingestion_queue_worker_error():
    with patch("src.ingestion.queue_manager.session_manager") as mock_manager:
        mock_session = AsyncMock()
        mock_manager.session.return_value.__aenter__.return_value = mock_session
        
        with patch("src.ingestion.queue_manager.IngestionService") as MockServiceArg:
            mock_service_instance = MockServiceArg.return_value
            mock_job = MagicMock(spec=IngestionJob)
            mock_job.id = "error-job-id"
            mock_job.file_path = "error.pdf"
            
            mock_service_instance.create_job = AsyncMock(return_value=mock_job)
            mock_service_instance.update_status = AsyncMock(return_value=mock_job)
            mock_service_instance.mark_failed = AsyncMock(return_value=mock_job)
            
            async def error_processor(file_path):
                raise ValueError("Processing failed")
                
            queue = IngestionQueue(error_processor)
            
            await queue.enqueue("error.pdf")
            await queue.start_worker()
            await asyncio.sleep(0.1)
            
            mock_service_instance.mark_failed.assert_called_with("error-job-id", "Processing failed")
            
            await queue.stop_worker()
