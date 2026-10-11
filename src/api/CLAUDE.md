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

- Every endpoint (except `/`, `/health`, `/v1/auth/*`) injects
  `user: UserContext = Depends(get_user_context)`.
- `UserContext` (Pydantic) carries `user_id`, `tenant_id`, optional `email`.
- `get_user_context` reads the JWT from the **`access_token` HttpOnly cookie**
  (set by the OAuth callback) — or, as a fallback, an `Authorization: Bearer`
  header for API clients/CLIs.
- When `AUTH_ENABLED=false` (local dev), `get_user_context` returns a synthetic
  context scoped to `DEFAULT_TENANT_ID` (the seed tenant from migration
  `5ac699391b63`). When `AUTH_ENABLED=true`, the JWT must carry `sub` and
  `tenant_id` claims or the request gets 401.
- Endpoints pass `user.tenant_id` into services. Service read methods
  (`get_by_id`, `list_jobs`, `list_conversations`, `get_conversation_with_messages`)
  take an optional `tenant_id` kwarg; when set, queries are scoped and
  cross-tenant rows return `None` → endpoint translates to 404 (no existence leak).

## OAuth login flow

`src/api/auth_routes.py` provides four routes under `/v1/auth`:

- `GET /v1/auth/login/{provider}` — Authlib redirects to Google or GitHub.
  Returns 503 if that provider's `OAUTH_*_CLIENT_ID`/`SECRET` are unset.
- `GET /v1/auth/callback/{provider}` — exchanges the code, fetches the
  user's email + subject, upserts a `User` (creates a personal `Tenant`
  on first login via `UserService.upsert_oauth_user`), mints a JWT, sets
  it as an HttpOnly `access_token` cookie (`SameSite=Lax`,
  `Secure=COOKIE_SECURE`, max-age = `JWT_EXPIRATION_MINUTES`), and 302's
  to `FRONTEND_URL`.
- `GET /v1/auth/me` — returns the current `UserContext` as JSON. SPA
  calls this on mount to bootstrap session state.
- `POST /v1/auth/logout` — clears the cookie.

`SessionMiddleware` is mounted so Authlib can stash the OAuth `state`
parameter between redirect and callback. Rotate `SESSION_SECRET` to
invalidate in-flight OAuth handshakes.

## Known Issues (fix when modifying this code)

- **Sync file I/O**: `open()` + `shutil.copyfileobj()` blocks event loop.
  Should use `aiofiles`.
- **No filename sanitization**: `file.filename` used directly in path.
  Path traversal risk.
- **No file size limit**: Uploads unchecked. Add `UploadFile` size validation.
- **No tenant invites / sharing**: every new OAuth user gets their OWN tenant.
  There's currently no way for two users to share a tenant short of admin
  DB surgery. Add `/v1/tenants/{id}/invite` when you need this.
- **Email-as-identity**: a second OAuth identity for an existing email returns
  409 instead of silently merging. Intentional — flag if you need linking.
- **Hardcoded DB URL**: `DATABASE_URL` defaults to localhost:5434.
