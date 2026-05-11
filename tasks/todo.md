# UniSensoryAI — Project Roadmap

## Phase 1: Stabilize Foundation (Current)
- [x] Fix hardcoded model_id in processor — thread from API → queue → processor
- [x] Create shared test fixtures (tests/conftest.py)
- [x] Add unit tests: processor, queue, models, config, converter, services, API
- [x] Create tasks/ tracking directory
- [ ] Verify all tests pass, lint clean, types clean

## Phase 2: Agents & Router
- [ ] Implement BaseRouter concrete class (route documents by DocumentType)
- [ ] Build PDFAgent (VLM-based page analysis)
- [ ] Build WordAgent (text extraction + VLM enrichment)
- [ ] Build PowerPointAgent (slide-by-slide processing)
- [ ] Build ImageAgent (direct VLM analysis)
- [ ] Complete ExcelParserAgent (replace mock with real VLM extraction)
- [ ] Wire agents into processing pipeline via router

## Phase 3: Pipeline Orchestration
- [ ] Implement BasePipelineStage concrete classes:
  - ingestion, validation, routing, parsing, content_validation, enrichment, formatting
- [ ] Enable switching between basic and advanced pipelines
- [ ] Add pipeline configuration validation

## Phase 4: Production Hardening
- [ ] Migrate logging to structlog (JSON format)
- [ ] Add timeout enforcement (30s agents, 15s tools, 60s inference)
- [ ] File validation (type/size checks, path sanitization, temp cleanup)
- [ ] Fix sync I/O in API (use aiofiles for file upload)
- [ ] Add filename sanitization (prevent path traversal)
- [ ] App Dockerfile + full docker-compose
- [ ] API authentication & inbound rate limiting (100 req/s)
- [ ] CORS configuration

## Phase 5: Advanced Features
- [ ] Multi-model ensemble (route doc types to specialized models)
- [ ] Chunk-based retrieval (leverage content_chunks in Document model)
- [ ] Webhook/callback notifications for job completion
- [ ] Batch processing endpoint
- [ ] Model cache eviction strategy (LRU or memory-based)
- [ ] Admin dashboard / monitoring

## Auth Upload Fix
- [x] Confirm why document extraction returns Bearer-token errors.
- [x] Add tests for local/dev auth defaults and explicit auth enforcement.
- [x] Update auth configuration with the smallest compatible behavior change.
- [x] Run targeted backend tests.
- [x] Run frontend build.

### Review
- Root cause: the frontend has no JWT/login flow, while `/v1/process_document` required auth by default.
- Result: auth is disabled unless `AUTH_ENABLED=true`; explicit production auth still requires a valid Bearer token.
- Verification: `uv run pytest -q tests/unit/test_auth.py`, `uv run pytest -q tests/unit/test_api.py`, and `npm.cmd run build` passed.

## Office Preview And Full Extraction Fix
- [x] Confirm DOCX source preview was gated as unsupported in the frontend.
- [x] Confirm Office text was being summarized by the model before being saved.
- [x] Preserve converted Office text as the extraction output.
- [x] Include DOCX table cell text in conversion.
- [x] Add Office text preview endpoint and render it in the original pane.
- [x] Run targeted backend tests.
- [x] Run frontend build.

### Review
- Root cause: browser inline preview only supported PDFs/images, and Office extraction used a "key information" model prompt that intentionally produced short summaries.
- Result: DOCX/PPTX/XLSX source previews now use backend text conversion, and new Office extractions save the full converted text.
- Verification: `uv run pytest -q tests/unit/test_pipeline_stages.py tests/unit/test_processor.py tests/unit/test_document_converter.py tests/unit/test_api.py` and `npm.cmd run build` passed.

## Split Preview And Policy Review Persistence
- [x] Add tests proving policy review results are persisted and retrievable.
- [x] Persist policy review results on the reviewed document.
- [x] Load saved policy review results when returning job/document data.
- [x] Remove nested original-preview scrollbars and add zoom controls.
- [x] Highlight uploaded-document contradiction clauses in the original preview.
- [x] Run targeted backend tests.
- [x] Run frontend build.

### Review
- Result: policy review results are stored as a reserved `policy_review_result` JSON chunk on the reviewed document and reloaded through job payloads plus `GET /v1/jobs/{job_id}/policy-review`.
- Preview UX: the original pane no longer wraps embedded previews in a second vertical scroller, and the preview has zoom controls for PDF, Office HTML, and images.
- Highlighting: uploaded-document clauses from policy findings are highlighted in Office HTML previews; PDF previews open with a search fragment for the first contradiction clause.
- Verification: `uv run pytest -q tests/unit/test_policy_service.py tests/unit/test_api.py` and `npm.cmd run build` passed.

## Full Markdown Extraction Results
- [x] Confirm the 503-character cap was coming from the jobs list serializer.
- [x] Update jobs list responses to return full extracted content.
- [x] Convert Office extracted text into Markdown-style structure.
- [x] Update image/PDF inference prompt to request faithful Markdown extraction.
- [x] Run targeted backend tests.
- [x] Run frontend build.

### Review
- Root cause: `GET /v1/jobs` still used a 500-character preview serializer, so dashboard-loaded documents could carry truncated extracted content.
- Result: job list and job detail payloads now expose full `content_text`; DOCX/XLSX/PPTX extraction preserves structure with Markdown headings/tables, and visual extraction prompts request faithful Markdown rather than summary text.
- Verification: `uv run pytest -q tests/unit/test_document_converter.py tests/unit/test_pipeline_stages.py`, `uv run pytest -q tests/unit/test_api.py`, and `npm.cmd run build` passed.

## Multi-Tenant Auth (OAuth + Tenants/Users)

**Goal:** Add real authentication (Google/GitHub OAuth) and tenant-scoped data isolation. Today `src/api/auth.py` has JWT scaffolding but no user store, no login endpoint, no tenant model, and `_user` is discarded by every endpoint that depends on it. Resources are globally visible.

**Decisions taken:**
- Tenancy: tenants ↔ users (many users per tenant). On first OAuth login, create a personal tenant for the user.
- Onboarding: OAuth only (Google + GitHub). No password auth, no signup form.
- Scope: backend + frontend login (React login page, protected routes, logout).
- Token transport: **HttpOnly cookie** holding the JWT. Avoids token-in-localStorage XSS exposure; backend sets the cookie on OAuth callback. `SameSite=Lax` is sufficient because OAuth callback is top-level navigation.
- Session model: stateless JWT, 60-min expiry, no refresh tokens in first pass. Re-login on expiry. (Revisit if friction surfaces.)

### Phase A — DB schema & migration (write tests first)
- [ ] `tests/unit/test_db_models_tenant_user.py` — Tenant + User CRUD, unique constraints, FK cascade
- [ ] Add `src/db/models/tenant.py` — `Tenant(id, name, slug UNIQUE, created_at, updated_at)`
- [ ] Add `src/db/models/user.py` — `User(id, tenant_id FK→tenants, email UNIQUE, name, oauth_provider, oauth_subject, role, created_at, last_login_at)`; composite UNIQUE on `(oauth_provider, oauth_subject)`
- [ ] Add `tenant_id` FK (NOT NULL, indexed) to `IngestionJob`, `Document`, `ChatConversation`. `Document.tenant_id` set on creation (denormalized — keeps queries flat; do NOT rely on join through job)
- [ ] Register new models in `src/db/models/__init__.py` and `alembic/env.py`
- [ ] Alembic migration: create `tenants`, `users`; add nullable `tenant_id` columns; backfill existing rows to a single seed tenant `default` + system user; flip columns to NOT NULL; add indexes. Single migration file, multi-step `op.execute`.

### Phase B — OAuth backend
- [ ] `tests/unit/test_auth_oauth.py` — mocked provider exchange, user upsert, JWT contents, cookie attributes
- [ ] Add Authlib dependency (`authlib>=1.3`) and `itsdangerous` (Starlette SessionMiddleware requirement for OAuth state)
- [ ] Env vars in `.env.example`: `OAUTH_GOOGLE_CLIENT_ID/SECRET`, `OAUTH_GITHUB_CLIENT_ID/SECRET`, `OAUTH_REDIRECT_BASE_URL`, `SESSION_SECRET`, `FRONTEND_URL`, default `AUTH_ENABLED=true`
- [ ] Extend `src/api/auth.py`:
  - `UserContext` Pydantic model (user_id, tenant_id, email) — typed replacement for `dict`
  - `create_access_token` includes `sub=user_id`, `tenant_id`, `email`
  - `get_current_user` → returns `UserContext`, reads JWT from `Cookie` header (`access_token`), falls back to `Authorization: Bearer` for API clients
  - When `AUTH_ENABLED=false`, return a synthetic dev `UserContext(tenant_id="dev", user_id="dev")` so tests + local dev still work
- [ ] New `src/api/auth_routes.py`:
  - `GET /v1/auth/login/{provider}` — Authlib redirect (google, github)
  - `GET /v1/auth/callback/{provider}` — exchange code, fetch userinfo, upsert User (create personal Tenant on first login), set HttpOnly cookie, 302 to `FRONTEND_URL`
  - `POST /v1/auth/logout` — clear cookie
  - `GET /v1/auth/me` — return current `UserContext` + tenant name
- [ ] Add `SessionMiddleware` (for OAuth state) and tighten `CORSMiddleware` (`allow_credentials=True` already set; restrict origins via env)

### Phase C — Tenant-scoped service layer (tests first)
- [ ] `tests/unit/test_tenant_isolation.py` — cross-tenant get returns None (endpoints will translate to 404), list excludes other tenants, create stamps tenant_id
- [ ] Extend `BaseService` with `_tenant_filter(stmt, tenant_id)` helper and require `tenant_id` on the service constructor: `IngestionService(db, tenant_id)`. Constructor-injection keeps every query consistent and avoids a forgotten-param bug.
- [ ] Update `IngestionService.create_job/list_jobs/get_by_id/update_status/fail_interrupted_jobs/delete` to filter/stamp tenant_id
- [ ] Update `ChatService` and `PolicyReviewService` similarly
- [ ] `process_document_job` (background worker) needs tenant_id propagated through queue meta — pass it into the job from the API and read it back when creating Document rows
- [ ] Cross-tenant access → service returns None; endpoints map to 404 (not 403, to avoid existence leak)

### Phase D — Endpoint wiring
- [ ] In `src/api/server.py`, replace every `Depends(get_db)` with a combined `Depends(get_user_scoped_db)` that yields `(db, user)` — or add `user: UserContext = Depends(get_current_user)` to every endpoint and pass `user.tenant_id` to service constructors
- [ ] Remove `_user` discard patterns. Every endpoint that touches user data takes a `UserContext`.
- [ ] Health endpoint (`/`, `/health`) stays public. `/v1/auth/*` stays public.
- [ ] Update `src/api/CLAUDE.md` — drop the "No authentication" known issue, document the new flow

### Phase E — Frontend integration
- [ ] `frontend/src/context/AuthContext.jsx` — fetches `/v1/auth/me` on mount, exposes `user`, `isAuthenticated`, `logout()`. No token handling in JS (cookie is HttpOnly).
- [ ] `frontend/src/api/client.js` — add `credentials: 'include'` to `apiFetch`; on 401, dispatch a logout event so the app routes to `/login`
- [ ] `frontend/src/pages/Login.jsx` — two buttons, each `<a href="/v1/auth/login/google">` / GitHub. No JS state needed for the redirect itself.
- [ ] `frontend/src/components/auth/ProtectedRoute.jsx` — wraps `AppShell`; redirects unauthenticated users to `/login`
- [ ] Update `App.jsx` to add `/login` route + wrap shell in `ProtectedRoute`; wrap app in `AuthProvider`
- [ ] `TopBar` — show user email + logout button
- [ ] Add Vite proxy for `/v1/auth/*` (already proxied if `/v1` is — verify)

### Phase F — Tests, lint, types
- [ ] `pytest tests/ -v --cov=src` — must pass; coverage on new code ≥ 80%
- [ ] `mypy src/` strict — clean
- [ ] `ruff check src/ tests/` and `black --check` — clean
- [ ] Frontend: `npm run build` — clean

### Phase G — Docs & cleanup
- [ ] Update `.env.example` with all new vars + a section explaining OAuth setup (Google Cloud Console + GitHub OAuth App redirect URIs)
- [ ] Update root `CLAUDE.md` architecture section (mention tenants/users)
- [ ] Append review section to this todo after implementation

### Explicit non-goals (this pass)
- Inviting other users to a tenant (admin UI / invite tokens)
- Per-resource sharing (cross-user grants)
- Roles beyond `member` (no admin/viewer distinction yet — schema supports it, UI does not)
- Refresh tokens / token revocation list
- Email/password auth, MFA, email verification (OAuth provider handles identity verification)
- Migration tooling for an existing prod DB beyond the seed-tenant backfill (this is still pre-prod data)

### Risks / things to watch
- **Cookie + CORS:** `allow_credentials=True` requires concrete origins, not `*`. Already concrete (`localhost:5173`) — keep it that way.
- **Background worker context:** the ingestion worker runs outside the request lifecycle. It must pull `tenant_id` from the queue meta, not from any request state, or stamped Documents will be wrong.
- **Backfill:** existing job/document/conversation rows have no real owner. Assigning them to a `default` tenant means whichever user first logs in does NOT inherit them — they'll be invisible. Acceptable for pre-prod; document it.
- **Endpoint coverage:** every endpoint must take `UserContext` — easy to miss one and leave a global-read hole. Phase D should be done by grep, not by memory: `rg "Depends\(get_db\)"` should return zero matches outside `/health` and `/v1/auth/*` when done.

### Review (Phases A + D only — agreed scope)

Reconciled with a previous session's partial work on the same feature and finished the half-done multi-tenancy data layer. OAuth (Phase B) and frontend (Phase E) were explicitly deferred.

**Phase A — schema + models** (reconciled)
- Discovered the previous session had already done the migration ([5ac699391b63](alembic/versions/5ac699391b63_add_tenants_users_and_tenant_id.py)) and services tenant-id kwargs, but had **not** created the ORM model files or added `tenant_id` columns to existing models — leaving the codebase in a broken state where the migration would apply but the ORM would crash.
- Added [src/db/models/tenant.py](src/db/models/tenant.py) and [src/db/models/user.py](src/db/models/user.py) with composite unique on `(oauth_provider, oauth_subject)`.
- Added `tenant_id: Mapped[str]` (NOT NULL, indexed FK) to `IngestionJob`, `Document`, `ChatConversation`.
- Registered new modules in [src/db/models/__init__.py](src/db/models/__init__.py) and [alembic/env.py](alembic/env.py).
- Deleted my duplicate migration `b2a1c4d9e5f0_*` (kept the pre-existing one).
- New test [tests/unit/test_db_models_tenant_user.py](tests/unit/test_db_models_tenant_user.py) — 6 ORM tests against in-memory SQLite, covering create, unique constraints (slug, email, oauth identity), and tenant↔user relationship.

**Auth scaffolding upgrade**
- Added a typed [`UserContext`](src/api/auth.py#L29) Pydantic model (user_id, tenant_id, email) and a `get_user_context` FastAPI dependency.
- `get_user_context` returns a synthetic context scoped to `DEFAULT_TENANT_ID` when `AUTH_ENABLED=false`, and validates JWT `sub` + `tenant_id` claims otherwise. Missing claims → 401.
- Kept `resolve_tenant_id` for backward compat; now accepts `UserContext | dict | None`.
- New test [tests/unit/test_auth_user_context.py](tests/unit/test_auth_user_context.py) — 11 tests covering model construction, synthetic-dev mode, missing creds, valid token, missing tenant claim, dict + UserContext + None inputs to `resolve_tenant_id`.

**Service layer — read-side tenant scoping**
- `IngestionService.get_by_id` and `list_jobs` now take an optional `tenant_id` kwarg ([src/services/ingestion.py](src/services/ingestion.py)); when set, queries filter by tenant. Kept as opt-in so background workers can still operate by job id.
- `ChatService.list_conversations` and `get_conversation_with_messages` got the same kwarg ([src/services/chat.py](src/services/chat.py)).

**Phase D — endpoint wiring**
- Replaced every `_user: dict = Depends(get_current_user)` discard with `user: UserContext = Depends(get_user_context)` in [src/api/server.py](src/api/server.py).
- All 18 non-health endpoints inject the user context. Verification: `rg "Depends\(get_db\)"` shows 15 hits in server.py, every one paired with a `Depends(get_user_context)` on the next line.
- Endpoints pass `user.tenant_id` to service read/write methods. Cross-tenant access returns `None` → 404, no existence leak.
- `update_conversation`, `delete_conversation`, `add_message` previously called `service.get_by_id(...)` (inherited BaseService — global). Switched to `service.get_conversation_with_messages(..., tenant_id=...)` for the existence check so cross-tenant updates/deletes return 404.
- Policy review endpoints (`GET`/`POST /v1/jobs/{job_id}/policy-review`) gained an `IngestionService` tenant guard before delegating to `PolicyReviewService` (which itself remains tenant-naive — acceptable since the guard runs first).

**Tenant-isolation tests (new)**
- [tests/unit/test_tenant_isolation.py](tests/unit/test_tenant_isolation.py) — 5 tests against in-memory SQLite proving:
  - `list_jobs` excludes other-tenant rows
  - `get_by_id` with wrong tenant returns None
  - `get_by_id` without tenant scope is still global (background-worker path)
  - `list_conversations` and `get_conversation_with_messages` enforce tenant separation

**Test results**
- `pytest -q --no-cov`: **251 passed, 1 failed**.
- The single failure ([tests/unit/test_document_converter.py::TestPdfConversion::test_convert_pdf](tests/unit/test_document_converter.py)) is a pre-existing test-isolation bug: `test_api.py` mocks `fitz`/`pymupdf` in `sys.modules`, which leaks into `test_document_converter.py` when the latter runs after. Passes in isolation. Unrelated to this work.

**Docs**
- Updated [src/api/CLAUDE.md](src/api/CLAUDE.md) — replaced "No authentication" issue with a description of the new flow, kept other known issues, added "no login endpoint" gap.
- Updated [.env.example](.env.example) with the new auth env vars (`DEFAULT_TENANT_ID`, `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `JWT_EXPIRATION_MINUTES`).

**Explicitly deferred (still TODO whenever OAuth ships)**
- `/v1/auth/login/{provider}`, `/v1/auth/callback/{provider}`, `/v1/auth/me`, `/v1/auth/logout` endpoints
- Authlib dependency + Google/GitHub OAuth client setup
- Frontend `AuthContext`, `Login.jsx`, `ProtectedRoute`, cookie-based token transport
- First-login auto-create-tenant logic
- Tightening CORS allow-list to env-driven
- Per-tenant invites / sharing / roles beyond `member`
