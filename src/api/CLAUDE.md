# src/api/ — FastAPI Endpoints

Async API with lifespan-managed startup/shutdown.

## Startup Order (lifespan context manager)

1. `init_db(DATABASE_URL)` — initialize session manager
2. `init_ingestion_queue(process_document_job)` — create queue
3. `queue.start_worker()` — start background worker task

## Endpoints

- `GET /` — Health check
- `POST /v1/process_document` — Upload file, returns 202 with `job_id`
- `GET /v1/jobs/{job_id}` — Fetch job status + document results

## Dependencies

- `Depends(get_db)` for session injection in endpoint functions
- All endpoints must be `async def`

## Known Issues (fix when modifying this code)

- **Sync file I/O**: `open()` + `shutil.copyfileobj()` blocks event loop (line 74).
  Should use `aiofiles`.
- **No filename sanitization**: `file.filename` used directly in path (line 70).
  Path traversal risk.
- **No file size limit**: Uploads unchecked. Add `UploadFile` size validation.
- **No authentication**: All endpoints open. Add FastAPI dependency-based auth.
- **No CORS**: Not configured. Add `CORSMiddleware` per environment.
- **Hardcoded DB URL**: `DATABASE_URL` defaults to localhost:5434 (line 27).
