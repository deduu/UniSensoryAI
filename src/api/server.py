from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Depends, Query, Request
from fastapi.responses import StreamingResponse, FileResponse
from src.api.validators import UploadValidator
from src.api.auth import get_current_user
from src.api.rate_limit import RateLimitDep
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pathlib import Path
from typing import Optional
import shutil
import os
import uuid
import json
import httpx
from contextlib import asynccontextmanager

# DB and Queuing imports
from src.db.session import init_db, get_db
from src.ingestion import init_ingestion_queue, get_ingestion_queue
from src.ingestion.converter import DocumentConverter
from src.ingestion.processor import process_document_job
from src.services.ingestion import IngestionService
from src.db.models.ingestion import IngestionStatus
from src.services.chat import ChatService
from src.services.exceptions import NotFoundException
from src.policy.models import PolicyReviewRequest
from src.policy.service import PolicyReviewService

# Setup structured logging
from src.utils.logging import configure_logging, get_logger

configure_logging(
    json_output=os.getenv("LOG_FORMAT", "console") == "json",
    log_level=os.getenv("LOG_LEVEL", "INFO"),
)
logger = get_logger("api")

# Load environment configs
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5433/unisensory")
UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _truncate_content(content: str | None, *, limit: int = 500) -> str | None:
    if content is None or len(content) <= limit:
        return content
    return f"{content[:limit]}..."


def _policy_review_from_chunks(chunks: list[dict] | None) -> dict | None:
    if not isinstance(chunks, list):
        return None
    for chunk in reversed(chunks):
        if not isinstance(chunk, dict):
            continue
        if chunk.get("type") == "policy_review_result":
            return chunk.get("result")
    return None


def _serialize_document(doc, *, truncate: bool = False) -> dict:
    content_text = _truncate_content(doc.content_text) if truncate else doc.content_text
    content_chunks = getattr(doc, "content_chunks", None)
    if not isinstance(content_chunks, list):
        content_chunks = None
    return {
        "id": doc.id,
        "filename": doc.filename,
        "content_text": content_text,
        "content_chunks": content_chunks,
        "policy_review": _policy_review_from_chunks(content_chunks),
    }

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
    request: Request,
    file: UploadFile = File(...),
    model_id: Optional[str] = Form("qwen3-vl-30b"),
    api_keys: Optional[str] = Form(None),
    start_page: Optional[int] = Form(None, ge=1),
    end_page: Optional[int] = Form(None, ge=1),
    _user: Optional[dict] = Depends(get_current_user),
    _rate_limit: None = Depends(RateLimitDep(requests_per_minute=100)),
) -> JSONResponse:
    """
    Submit a document for asynchronous processing.
    """
    if start_page and end_page and start_page > end_page:
        raise HTTPException(status_code=400, detail="Start page cannot be greater than end page.")

    # Validate upload
    await UploadValidator.validate(file)

    try:
        # Prefix with UUID to prevent filename collisions on re-upload
        safe_filename = f"{uuid.uuid4()}_{file.filename}"
        file_path = UPLOAD_DIR / safe_filename

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Parse api keys if provided
        keys_dict = None
        if api_keys:
            try:
                keys_dict = json.loads(api_keys)
            except Exception as e:
                logger.warning(f"Failed to parse api_keys json: {e}")
                
        # Enqueue
        queue = get_ingestion_queue()
        meta = {
            "model_id": model_id,
            "original_filename": file.filename,  # preserve human-readable name
        }
        if keys_dict:
            meta["api_keys"] = keys_dict
        if start_page:
            meta["start_page"] = start_page
        if end_page:
            meta["end_page"] = end_page
            
        try:
            meta["file_size"] = file_path.stat().st_size
        except Exception:
            pass
            
        job_id = await queue.enqueue(str(file_path.absolute()), meta=meta)
        
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
                    _serialize_document(doc)
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
                _serialize_document(doc)
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


@app.get("/v1/jobs/{job_id}/file")
async def serve_job_file(job_id: str, db=Depends(get_db)):
    """Serve the original uploaded file for a job."""
    service = IngestionService(db)
    try:
        job = await service.get_by_id(job_id, raise_not_found=False)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        file_path = Path(job.file_path)
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found on disk")

        original_filename = job.meta.get("original_filename", file_path.name) if job.meta else file_path.name
        # No `filename` arg — avoids Content-Disposition: attachment so browsers render inline
        response = FileResponse(path=str(file_path))
        response.headers["Content-Disposition"] = f'inline; filename="{original_filename}"'
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving file for job {job_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# SSE — Real-time job status stream
# ---------------------------------------------------------------------------

@app.get("/v1/jobs/{job_id}/preview")
async def preview_job_file(job_id: str, db=Depends(get_db)):
    """Return text preview content for Office source files."""
    service = IngestionService(db)
    try:
        job = await service.get_by_id(job_id, raise_not_found=False)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        file_path = Path(job.file_path)
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found on disk")

        ext = file_path.suffix.lower()
        if ext not in {".docx", ".pptx", ".xlsx"}:
            raise HTTPException(
                status_code=400,
                detail="Preview text is only available for Office files",
            )

        content_items = DocumentConverter.convert(file_path)
        original_filename = job.meta.get("original_filename", file_path.name) if job.meta else file_path.name
        return JSONResponse(
            content={
                "filename": original_filename,
                "content_type": "text/plain",
                "content": "\n\n".join(str(item) for item in content_items),
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error previewing file for job {job_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/jobs/{job_id}/preview/html", response_class=None)
async def preview_job_file_html(job_id: str, db=Depends(get_db)):
    """Return an HTML document for browser-native Office file preview (DOCX, XLSX, PPTX)."""
    from fastapi.responses import HTMLResponse

    service = IngestionService(db)
    try:
        job = await service.get_by_id(job_id, raise_not_found=False)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        file_path = Path(job.file_path)
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found on disk")

        ext = file_path.suffix.lower()
        if ext not in {".docx", ".pptx", ".xlsx"}:
            raise HTTPException(status_code=400, detail="HTML preview only available for Office files")

        html = DocumentConverter.to_html(file_path)
        return HTMLResponse(content=html)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating HTML preview for job {job_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/jobs/{job_id}/stream")
async def stream_job_status(
    job_id: str,
    _user: Optional[dict] = Depends(get_current_user),
):
    """Stream job status updates via Server-Sent Events."""
    from src.api.events import job_status_stream

    return StreamingResponse(
        job_status_stream(job_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Chat — Conversation & Message CRUD
# ---------------------------------------------------------------------------

@app.post("/v1/chat/conversations")
async def create_conversation(request: Request, db=Depends(get_db)):
    """Create a new chat conversation."""
    body = await request.json()
    service = ChatService(db)
    try:
        conv = await service.create_conversation(
            title=body.get("title", "New conversation"),
            model_id=body.get("model_id"),
            temperature=body.get("temperature", 0.7),
            thinking_enabled=body.get("thinking_enabled", False),
            streaming_enabled=body.get("streaming_enabled", True),
            grounded_document_ids=body.get("grounded_document_ids"),
        )
        await db.commit()
        return JSONResponse(status_code=201, content={
            "id": conv.id,
            "title": conv.title,
            "model_id": conv.model_id,
            "temperature": conv.temperature,
            "thinking_enabled": conv.thinking_enabled,
            "streaming_enabled": conv.streaming_enabled,
            "grounded_document_ids": conv.grounded_document_ids,
            "created_at": conv.created_at.isoformat(),
            "updated_at": conv.updated_at.isoformat(),
        })
    except Exception as e:
        logger.error(f"Error creating conversation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/chat/conversations")
async def list_conversations(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db=Depends(get_db),
):
    """List all chat conversations."""
    service = ChatService(db)
    try:
        convs = await service.list_conversations(limit=limit, offset=offset)
        return JSONResponse(content=[
            {
                "id": c.id,
                "title": c.title,
                "model_id": c.model_id,
                "created_at": c.created_at.isoformat(),
                "updated_at": c.updated_at.isoformat(),
            }
            for c in convs
        ])
    except Exception as e:
        logger.error(f"Error listing conversations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/chat/conversations/{conversation_id}")
async def get_conversation(conversation_id: str, db=Depends(get_db)):
    """Get a conversation with all its messages."""
    service = ChatService(db)
    try:
        conv = await service.get_conversation_with_messages(conversation_id)
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return JSONResponse(content={
            "id": conv.id,
            "title": conv.title,
            "model_id": conv.model_id,
            "temperature": conv.temperature,
            "thinking_enabled": conv.thinking_enabled,
            "streaming_enabled": conv.streaming_enabled,
            "grounded_document_ids": conv.grounded_document_ids,
            "created_at": conv.created_at.isoformat(),
            "updated_at": conv.updated_at.isoformat(),
            "messages": [
                {
                    "id": m.id,
                    "role": m.role,
                    "content": m.content,
                    "thinking_content": m.thinking_content,
                    "prompt_tokens": m.prompt_tokens,
                    "completion_tokens": m.completion_tokens,
                    "total_tokens": m.total_tokens,
                    "latency_ms": m.latency_ms,
                    "model_used": m.model_used,
                    "citations": m.citations,
                    "created_at": m.created_at.isoformat(),
                }
                for m in conv.messages
            ],
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching conversation {conversation_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/v1/chat/conversations/{conversation_id}")
async def update_conversation(conversation_id: str, request: Request, db=Depends(get_db)):
    """Update a conversation's settings."""
    body = await request.json()
    service = ChatService(db)
    try:
        conv = await service.get_by_id(conversation_id, raise_not_found=False)
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")

        allowed = {"title", "model_id", "temperature", "thinking_enabled",
                    "streaming_enabled", "grounded_document_ids"}
        updates = {k: v for k, v in body.items() if k in allowed}
        conv = await service.update_conversation(conversation_id, **updates)
        await db.commit()
        return JSONResponse(content={"detail": "Conversation updated", "id": conv.id})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating conversation {conversation_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/v1/chat/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, db=Depends(get_db)):
    """Delete a conversation and all its messages."""
    service = ChatService(db)
    try:
        conv = await service.get_by_id(conversation_id, raise_not_found=False)
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
        await service.delete_conversation(conversation_id)
        await db.commit()
        return JSONResponse(content={"detail": "Conversation deleted"})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting conversation {conversation_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/chat/conversations/{conversation_id}/messages")
async def add_message(conversation_id: str, request: Request, db=Depends(get_db)):
    """Add a message to a conversation."""
    body = await request.json()
    service = ChatService(db)
    try:
        conv = await service.get_by_id(conversation_id, raise_not_found=False)
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")

        msg = await service.add_message(
            conversation_id=conversation_id,
            role=body.get("role", "user"),
            content=body.get("content", ""),
            thinking_content=body.get("thinking_content"),
            prompt_tokens=body.get("prompt_tokens"),
            completion_tokens=body.get("completion_tokens"),
            total_tokens=body.get("total_tokens"),
            latency_ms=body.get("latency_ms"),
            model_used=body.get("model_used"),
            citations=body.get("citations"),
        )
        await db.commit()
        return JSONResponse(status_code=201, content={
            "id": msg.id,
            "conversation_id": msg.conversation_id,
            "role": msg.role,
            "content": msg.content,
            "created_at": msg.created_at.isoformat(),
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding message: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Policy Review — parallel post-ingestion analysis
# ---------------------------------------------------------------------------


@app.get("/v1/jobs/{job_id}/policy-review")
async def get_job_policy_review(job_id: str, db=Depends(get_db)):
    """Return the latest persisted policy review result for a completed job."""
    service = PolicyReviewService(db)
    try:
        result = await service.get_saved_review(job_id)
        if result is None:
            raise HTTPException(status_code=404, detail="No saved policy review for this job")
        return JSONResponse(content=result.model_dump())
    except HTTPException:
        raise
    except NotFoundException:
        raise HTTPException(status_code=404, detail="Job not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error loading policy review for job {job_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/jobs/{job_id}/policy-review")
async def review_job_policy(
    job_id: str,
    review_request: PolicyReviewRequest,
    db=Depends(get_db),
):
    """Run parallel policy review agents against a completed parsed document."""
    service = PolicyReviewService(db)
    try:
        result = await service.review_job(job_id, review_request)
        return JSONResponse(content=result.model_dump())
    except NotFoundException:
        raise HTTPException(status_code=404, detail="Job not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error reviewing policy for job {job_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Chat completions proxy — keeps API keys server-side
# ---------------------------------------------------------------------------

@app.post("/v1/chat/completions/stream")
async def proxy_chat_stream(request: Request):
    """
    Proxy OpenAI-compatible chat completions through the backend.
    Uses OPENAI_API_KEY / OPENAI_API_BASE from .env first;
    falls back to user-supplied keys from the request body.
    """
    body = await request.json()

    # .env takes priority; request body is fallback
    api_key = os.getenv("OPENAI_API_KEY") or body.get("api_key", "")
    api_base = (
        os.getenv("OPENAI_API_BASE")
        or body.get("api_base", "")
        or "https://api.openai.com/v1"
    ).rstrip("/")

    if not api_key:
        raise HTTPException(
            status_code=400,
            detail="No OpenAI API key configured. Set OPENAI_API_KEY in .env or provide it in Settings.",
        )

    payload = {
        "model": body.get("model", "gpt-4o"),
        "messages": body.get("messages", []),
        "temperature": body.get("temperature", 0.7),
        "max_tokens": body.get("max_tokens", 4096),
        "stream": True,
    }

    async def event_stream():
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream(
                    "POST",
                    f"{api_base}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                ) as resp:
                    if resp.status_code != 200:
                        error_body = await resp.aread()
                        yield f"data: {json.dumps({'error': error_body.decode()})}\n\n"
                        return
                    async for chunk in resp.aiter_text():
                        yield chunk
        except httpx.TimeoutException:
            yield f"data: {json.dumps({'error': 'Request timed out'})}\n\n"
        except Exception as e:
            logger.error(f"Chat proxy error: {e}", exc_info=True)
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8010)
