# src/ingestion/ — Document Ingestion Pipeline

Async queue with rate limiting, document conversion, and model caching.

## Components
- **DocumentConverter**: Static class. Returns `List[Image.Image]` for PDF/images,
  `List[str]` for Office files. `convert()` is synchronous (blocks on disk I/O).
- **IngestionQueue**: `asyncio.Queue` + single background worker task.
  Uses `RateLimiter` (token bucket: 10 req/s, burst 10).
- **processor.py**: `process_document_job()` — the actual processing function.

## Job Lifecycle
`enqueue()` → PENDING → `_worker()` → PROCESSING → COMPLETED / FAILED

## Model Cache
- `MODEL_CACHE`: global dict in `processor.py`, guarded by `MODEL_LOCK` (asyncio.Lock)
- Unbounded — no eviction. Models stay in memory for server lifetime.
- `model.process()` is NOT async — wrapped in `loop.run_in_executor(None, ...)`

## Session Pattern
- Each job gets its own DB session via `db_session.session_manager.session()`
- Late-binding import: `import src.db.session as db_session` (line 7 of queue_manager.py)
- Caller must `await session.commit()` — no auto-commit

## Gotchas
- **Mixed return types**: DocumentConverter returns Union[Image, str] per item.
  `processor.py` type-checks with `isinstance()` to pick text vs visual path.
- **Hardcoded model**: `processor.py:59` defaults to `"qwen2-vl-2b-instruct"`.
  Ignores `model_id` from job metadata (not yet wired).
- **Worker error recovery**: Exceptions are caught, job marked FAILED, loop continues.
  Worker sleeps 1s on unexpected errors to prevent tight loop.
