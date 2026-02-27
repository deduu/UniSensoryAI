from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pathlib import Path
from typing import Optional, Dict, Any
import shutil
import os
import logging
import uuid
from contextlib import asynccontextmanager

from src.utils.config import ConfigLoader
from src.models import ModelLoader
from src.core.document import Document, DocumentType

# DB and Queuing imports
from src.db.session import init_db, get_db, session_manager
from src.ingestion import init_ingestion_queue, get_ingestion_queue
from src.ingestion.processor import process_document_job
from src.services.ingestion import IngestionService
from src.db.models.ingestion import IngestionStatus

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api")

# Load environment configs
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5433/unisensory")
UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Initializing Database...")
    init_db(DATABASE_URL)
    
    logger.info("Initializing Ingestion Queue...")
    queue = init_ingestion_queue(process_document_job)
    await queue.start_worker()
    
    yield
    
    # Shutdown
    logger.info("Shutting down Ingestion Queue...")
    await queue.stop_worker()

app = FastAPI(
    title="UniSensoryAI Document Processing API",
    description="OpenAI-compatible API for multi-modal document understanding",
    version="0.1.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
@app.get("/health")
async def root():
    """Health check endpoint."""
    return {"status": "healthy", "service": "UniSensoryAI"}

@app.post("/v1/process_document")
async def process_document(
    file: UploadFile = File(...),
    model_id: Optional[str] = Form("qwen3-vl-30b"),
    # output_format: Optional[str] = Form("json") # Handled in retrieval now
) -> JSONResponse:
    """
    Submit a document for asynchronous processing.
    """
    try:
        # Prefix with UUID to prevent filename collisions on re-upload
        safe_filename = f"{uuid.uuid4()}_{file.filename}"
        file_path = UPLOAD_DIR / safe_filename

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Enqueue
        queue = get_ingestion_queue()
        # meta can pass model preference
        job_id = await queue.enqueue(str(file_path.absolute()), meta={"model_id": model_id})
        
        return JSONResponse(
            status_code=202,
            content={
                "job_id": job_id,
                "status": "queued",
                "message": "Document accepted for processing."
            }
        )
        
    except Exception as e:
        logger.error(f"Upload failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/v1/jobs")
async def list_jobs(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db=Depends(get_db),
):
    """List all jobs with pagination."""
    service = IngestionService(db)
    try:
        jobs = await service.list_jobs(limit=limit, offset=offset)
        return JSONResponse(content=[
            {
                "job_id": job.id,
                "status": job.status.value,
                "created_at": job.created_at.isoformat(),
                "updated_at": job.updated_at.isoformat(),
                "file_path": job.file_path,
                "meta": job.meta,
                "documents": [
                    {
                        "id": doc.id,
                        "filename": doc.filename,
                        "content_text": doc.content_text[:500] + "..." if doc.content_text else None,
                    }
                    for doc in job.documents
                ],
            }
            for job in jobs
        ])
    except Exception as e:
        logger.error(f"Error listing jobs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/jobs/{job_id}")
async def get_job_status(job_id: str, db=Depends(get_db)):
    """Get the status and result of a processing job."""
    service = IngestionService(db)
    try:
        job = await service.get_by_id(job_id, raise_not_found=False)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        response = {
            "job_id": job.id,
            "status": job.status.value,
            "created_at": job.created_at.isoformat(),
            "updated_at": job.updated_at.isoformat(),
            "file_path": job.file_path,
            "meta": job.meta,
            "documents": [
                {
                    "id": doc.id,
                    "filename": doc.filename,
                    "content_text": doc.content_text[:500] + "..." if doc.content_text else None,
                }
                for doc in job.documents
            ],
        }

        return JSONResponse(content=response)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching job {job_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/v1/jobs/{job_id}")
async def delete_job(job_id: str, db=Depends(get_db)):
    """Delete a job and its documents, clean up uploaded file."""
    service = IngestionService(db)
    try:
        job = await service.get_by_id(job_id, raise_not_found=False)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        # Clean up uploaded file from disk
        try:
            file_path = Path(job.file_path)
            if file_path.exists():
                file_path.unlink()
        except OSError as file_err:
            logger.warning(f"Could not delete file {job.file_path}: {file_err}")

        # Cascade deletes documents
        await service.delete(job_id)
        await db.commit()

        return JSONResponse(content={"detail": "Job deleted"})

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting job {job_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/jobs/{job_id}/retry")
async def retry_job(job_id: str, db=Depends(get_db)):
    """Retry a failed job by re-enqueuing it."""
    service = IngestionService(db)
    try:
        job = await service.get_by_id(job_id, raise_not_found=False)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        if job.status != IngestionStatus.FAILED:
            raise HTTPException(
                status_code=400,
                detail=f"Only failed jobs can be retried. Current status: {job.status.value}",
            )

        # Reset status and clear error from meta
        meta = dict(job.meta) if job.meta else {}
        meta.pop("error", None)
        await service.update_status(job_id, IngestionStatus.PENDING, meta)
        await db.commit()

        # Re-enqueue
        queue = get_ingestion_queue()
        await queue.queue.put(job_id)
        logger.info(f"Retried job {job_id}")

        return JSONResponse(content={
            "job_id": job_id,
            "status": "PENDING",
            "message": "Job re-queued for processing.",
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrying job {job_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8010)
