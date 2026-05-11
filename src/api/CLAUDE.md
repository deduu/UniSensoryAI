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

## Auth & Tenancy

- Every endpoint (except `/`, `/health`) injects `user: UserContext = Depends(get_user_context)`.
- `UserContext` (Pydantic) carries `user_id`, `tenant_id`, optional `email`.
- When `AUTH_ENABLED=false` (local dev), `get_user_context` returns a synthetic
  context scoped to `DEFAULT_TENANT_ID` (the seed tenant from migration
  `5ac699391b63`). When `AUTH_ENABLED=true`, the JWT must carry `sub` and
  `tenant_id` claims or the request gets 401.
- Endpoints pass `user.tenant_id` into services. Service read methods
  (`get_by_id`, `list_jobs`, `list_conversations`, `get_conversation_with_messages`)
  take an optional `tenant_id` kwarg; when set, queries are scoped and
  cross-tenant rows return `None` → endpoint translates to 404 (no existence leak).
- OAuth login flow is **not yet implemented** — tokens must be minted externally.

## Known Issues (fix when modifying this code)

- **Sync file I/O**: `open()` + `shutil.copyfileobj()` blocks event loop.
  Should use `aiofiles`.
- **No filename sanitization**: `file.filename` used directly in path.
  Path traversal risk.
- **No file size limit**: Uploads unchecked. Add `UploadFile` size validation.
- **No login endpoint**: JWT verification works but there's no `/v1/auth/login` —
  tokens must be created out-of-band (see `create_access_token` in `auth.py`).
- **CORS**: configured but allow-list is hardcoded to `localhost:5173`.
  Make env-driven before deploying.
- **Hardcoded DB URL**: `DATABASE_URL` defaults to localhost:5434.
