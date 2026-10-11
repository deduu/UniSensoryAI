# UniSensoryAI — Project Roadmap

## Checkpoint before extraction refactor — 2026-10-11

- [x] Review tracked/untracked changes and the unpublished commit; exclude secrets and generated artifacts.
- [x] Run bounded validation and record passing checks and unresolved limits.
- [x] Create `codex/checkpoint-before-extraction-refactor`, stage the intended snapshot, and commit it.
- [x] Push the checkpoint branch and verify its remote commit and local status.

### Review

Scope is a recoverable work-in-progress snapshot of the existing OAuth/frontend, extraction, chat/policy, and deployment work. Retains the unpublished orchestration commit `f0aba0a` in its ancestry. The extraction refactor is deferred.

- Review: two focused read-only reviews plus deployment/source inspection. Credential-pattern scan covered 91 outgoing files with no matches. Real `.env`, uploads, dependencies, frontend build output, and caches remain excluded by Git ignore rules.
- Verification: `git diff --check` passed; syntax checks passed for 67 outgoing Python files; 63 focused synchronous tests passed (33 async tests deselected); 81 focused workflow/auth tests passed (one Google metadata network test excluded). These two test runs overlap and are not an aggregate unique-test count.
- Frontend: `npm run build` passed. The initial sandboxed run failed resolving `index.html` with EPERM; the authorized retry outside the sandbox succeeded. Existing bundle-size/Browserslist warnings remain.
- Async verification: the authorized retry outside the sandbox completed successfully, resolving the earlier walkthrough's runner-stall limitation for this focused subset. No full-suite, lint/type, live model/database, or Docker deployment validation is claimed.
- Dependency limit: `uv.lock` still lists heavy ML packages as core dependencies and lacks the new `local-vlm` extra; lock metadata does not match `pyproject.toml`.
- Auth/frontend limits: cross-origin chat fetch lacks cookie credentials; explicit empty backend URL overrides can bypass the Vite API default; cached extracted jobs are not cleared/scoped on account switches; combined document/web citation indexes can identify the wrong source.
- Extraction limits: uploads still select `basic`; advanced stages are not API-selectable; structured validation diagnostics can include document values in logs and are not fully persisted; critic failures can appear as no findings; basic range chunks use ordinal page numbers.
- Publication: snapshot commit `b5034f282efc98c2f248e23684f6c4f788012b62` pushed to `origin/codex/checkpoint-before-extraction-refactor`. `git ls-remote` confirmed the exact remote hash; local status was clean and tracking the branch. A documentation follow-up records this verified completion.

## Product-owner codebase walkthrough — 2026-10-11

- [x] Trace a concrete business scenario through the current working tree.
- [x] Separate business concepts, runtime components, and code organization.
- [x] Cross-check active functionality and implementation limits against source and tests.
- [x] Deliver a business-first explanation and a recommended code-reading path.

### Review

- Used the repository's Acme existing/proposed AI policy demo to ground the business journey.
- Verified upload/extraction/persistence, on-demand policy review, and document-grounded chat with direct source inspection and three focused read-only explorations.
- Distinguished active basic extraction from registered advanced stages and unused document routing; distinguished current UI routes from leftover page files.
- Identified product limits: automatic recent-document reference selection, missing tenant scope on policy comparison references, bounded chat document context, incomplete streaming/tool use, and memory-queue/error handling gaps.
- Inspected representative test contracts; did not execute tests or a live model/database workflow for this explanatory task. Only this tracking section was changed; existing application work was preserved.

## Codebase architecture walkthrough — 2026-10-11

- [x] Trace the current runtime entry points and repository structure.
- [x] Map document extraction, policy review, and chat orchestration with their inputs and outputs.
- [x] Verify representative flows against focused tests and identify implementation limits.
- [x] Explain the architecture with a diagram, examples, and a suggested reading order.

### Review

- Traced the current working tree with three read-only explorations plus direct source inspection.
- Normal uploads select the basic stage pipeline; advanced stages and document routing are not connected to that upload path. Chat and policy use separate orchestration implementations.
- Verified source/test contracts for extraction, structured chunks, chat routing, policy findings, and persistence. Configuration/schema subset: 33 tests passed using the system Python interpreter.
- Async workflow tests stalled at the first async test in this environment, including with plugin autoload disabled and the Windows selector policy; stopped the runs. No live model/API/database processing was verified.
- Delivered an architecture diagram, repository map, example inputs/outputs, active-path caveats, and reading order in chat. Application source and existing application changes were preserved.

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
- ~~`/v1/auth/login/{provider}`, `/v1/auth/callback/{provider}`, `/v1/auth/me`, `/v1/auth/logout` endpoints~~ (shipped — see Phase B review below)
- ~~Authlib dependency + Google/GitHub OAuth client setup~~ (shipped)
- ~~Frontend `AuthContext`, `Login.jsx`, `ProtectedRoute`, cookie-based token transport~~ (shipped — see Phase E review below)
- ~~First-login auto-create-tenant logic~~ (shipped in `UserService.upsert_oauth_user`)
- ~~Tightening CORS allow-list to env-driven~~ (shipped — `CORS_ALLOW_ORIGINS`)
- Per-tenant invites / sharing / roles beyond `member` — **still open**

### Review (Phases B + E — OAuth backend + frontend login)

**Phase B — OAuth backend**
- Added [`UserService.upsert_oauth_user`](src/services/user.py) — looks up `(oauth_provider, oauth_subject)` and either updates `name`/`last_login_at` or creates a fresh user + personal tenant. Tenant slug is derived from the email local-part (e.g. `alice@acme.com` → `alice`); slug collisions get a short hex suffix.
- Treats email as globally unique — a second OAuth identity claiming an existing email returns 409, not a silent account-link.
- 4 tests in [test_user_service.py](tests/unit/test_user_service.py) cover first login, repeat login, cross-provider email collision, slug collision.
- Added [src/api/auth_routes.py](src/api/auth_routes.py): `/v1/auth/login/{provider}`, `/v1/auth/callback/{provider}`, `/v1/auth/me`, `/v1/auth/logout`. Providers without credentials return 503 instead of crashing.
- JWT now travels as an **HttpOnly cookie** (`access_token`, `SameSite=Lax`, `Secure=COOKIE_SECURE`). `get_user_context` reads the cookie first and falls back to `Authorization: Bearer` for non-browser clients.
- `SessionMiddleware` mounted (for Authlib's state token). CORS allow-list is now env-driven (`CORS_ALLOW_ORIGINS`).
- Added [authlib>=1.3](pyproject.toml) and [itsdangerous>=2.1](pyproject.toml). 7 tests in [test_auth_routes.py](tests/unit/test_auth_routes.py) cover unknown provider → 404, unconfigured provider → 503, login redirect, callback cookie issuance, `/me`, logout cookie clearing, and a full callback → `/me` cookie round-trip.

**Phase E — Frontend login**
- [AuthContext](frontend/src/context/AuthContext.jsx) calls `/v1/auth/me` on mount and exposes `{user, isAuthenticated, loading, refresh, logout}`. Listens for the `auth:expired` window event so any 401 anywhere clears the session.
- [apiFetch](frontend/src/api/client.js) now sends `credentials: 'include'` by default and dispatches `auth:expired` on 401 — so callers don't each handle re-auth.
- [Login.jsx](frontend/src/pages/Login.jsx) renders two `<a href="/v1/auth/login/{google|github}">` buttons — no JS token plumbing, just a top-level navigation.
- [ProtectedRoute.jsx](frontend/src/components/auth/ProtectedRoute.jsx) wraps `AppShell`; unauthenticated users get redirected to `/login` (with `state.from` for future return-to-where-you-were).
- [Sidebar.jsx](frontend/src/components/layout/Sidebar.jsx) account menu now shows the real `user.email` and the Sign-out button calls `logout()` + redirects.
- [App.jsx](frontend/src/App.jsx) registers `/login` and wraps the shell in `ProtectedRoute`. `useJobList()` moved from `App` into `AppShell` so it only fires once authenticated (avoids 401-noise on the login page).
- `vite build` clean. `npm run dev` proxies `/v1` to backend `:8010` unchanged.

**Test results**
- `pytest -q --no-cov` (full suite): **409 passed, 4 failed**.
- All 4 failures are **pre-existing on `main`** — verified by stashing my changes and re-running. They are DOCX/XLSX/PDF fixture-file generation breaking in this environment (`zipfile.BadZipFile`) plus the `fitz` mock-leakage already documented. Zero regressions from this work.
- Auth/tenant subset: **88/88 pass** (test_auth, test_auth_user_context, test_auth_routes, test_user_service, test_tenant_isolation, test_db_models_tenant_user, test_api, test_services).

**How to enable in real life**
1. Create Google OAuth client; add `http://localhost:8010/v1/auth/callback/google` as authorized redirect URI.
2. Same for GitHub OAuth App at `http://localhost:8010/v1/auth/callback/github`.
3. Fill the four `OAUTH_*_CLIENT_ID/SECRET` env vars + a strong `SESSION_SECRET` and `JWT_SECRET_KEY`.
4. Set `AUTH_ENABLED=true`. Set `COOKIE_SECURE=true` in production (HTTPS).
5. Visit `/login` in the SPA → click Sign in with Google → land back on `/`.

**Still open**
- Tenant invites / cross-user sharing / roles beyond `member` (schema supports `role`, UI does not).
- Refresh tokens / token revocation list (currently re-login on JWT expiry).
- Account-linking flow (right now Google + GitHub identities for the same email return 409).
- Hardening: rate-limit `/v1/auth/login/*`, log failed logins, rotate `JWT_SECRET_KEY` procedure.

## Modular Chat Orchestration (Pormetheus-style framework + web search)

Plan: [plans/in-chat-orchestration-do-elegant-anchor.md](../../.claude/plans/in-chat-orchestration-do-elegant-anchor.md). Goal — replace the pass-through chat proxy with a hybrid-routed pipeline (analyzer → direct | research+synthesize | fn-call) using a reusable framework that mirrors Pormetheus's `core/` layout.

### Status
- Framework + chat agents + composition root + endpoint integration were already built and committed in [f0aba0a](https://github.com/anthropics/claude-code) `feat(orchestration): modular agent framework with hybrid-routed chat + pluggable web search`. **80 orchestration/chat tests pass** (interfaces, models, strategies, web tools, circuit breaker, chat agents, ChatPipeline, ChatOrchestrationService, LLM providers).
- Live endpoint [POST /v1/chat/completions/stream](../src/api/server.py#L841) now routes through `ChatOrchestrationService` and emits an extra `data: {sources, citations, query_type, refined_queries}` SSE frame just before `[DONE]`. `bypass_orchestration=true` in the request body falls back to the original pass-through proxy for debugging.

### This session — finish + polish
- [x] Policy migration: [src/policy/web_search.py](../src/policy/web_search.py) is now a 120-line backwards-compat shim delegating to `src.orchestration.tools.web.providers.duckduckgo` and `ContentFetcher`. 22 policy tests (`test_policy_web_search`, `test_policy_orchestration`, `test_policy_service`, `test_policy_llm_agent`) still pass.
- [x] Frontend SSE parser: [streamBackendCompletion](../frontend/src/api/chat.js) detects the orchestration `sources`/`citations` frame and yields it as a distinct chunk shape. [useChat](../frontend/src/hooks/useChat.js) merges web citations with doc-context citations and pushes them to `streamingCitations` so badges render live. `vite build` clean.

### Deviation from plan
- **`configs/orchestration.yaml` was NOT added.** Composition reads from env vars (`OPENAI_API_KEY`, `WEB_SEARCH_PROVIDER`, `BRAVE_API_KEY`, `WEB_SEARCH_MAX_RESULTS`, `WEB_RESEARCH_MAX_PAGES`, `CHAT_ORCHESTRATION_TIMEOUT`) via [`ChatSettings.from_env`](../src/chat/composition.py). Matches the project's existing env-driven auth/db config style — adding YAML on top would be redundant. If you want explicit YAML later, extend `ChatSettings` with a `from_yaml` classmethod and read `configs/orchestration.yaml` via `ConfigLoader`.

### Architecture notes
- New tree:
  - [src/orchestration/](../src/orchestration/) — generic framework. Tool/Agent ABCs, Orchestrator + Strategy Protocol, Single/Router/Pipeline/Parallel strategies, CircuitBreaker, OpenAI-compatible LLM client.
  - [src/orchestration/tools/web/](../src/orchestration/tools/web/) — `SearchProvider` ABC + DuckDuckGo and Brave implementations, `ContentFetcher`, `WebSearchTool` (Tool-shaped, used by function-calling).
  - [src/chat/](../src/chat/) — chat application: four agents + composite `ChatPipelineAgent` + `build_chat_orchestrator` composition root + `ChatOrchestrationService` facade.
- Decision flow per request: `QueryAnalyzerAgent` classifies as `direct | search | ambiguous`. `direct` → `DirectAnswererAgent`. `search` → `WebResearcherAgent` (parallel page fetch) → `SynthesizerAgent` (inline `[N]` citations). `ambiguous` → `DirectAnswererAgent` with `web_search` exposed as an OpenAI function tool.
- Provider failures are wrapped in a 3-fail / 60s `CircuitBreaker`. Half-open probe success closes the breaker; failure re-opens. Per-page fetch errors don't kill the research run — the source row stays with snippet only.

### Pre-existing test failures (NOT caused by this work)
- `test_document_converter::test_convert_pdf`, `test_pipeline_stages::TestConversionStage::test_passes_page_range` / `test_raises_on_empty_content`, `test_processor::test_process_document_job_text_processing` — all four fail with my changes stashed too. Same `zipfile.BadZipFile` + `fitz`-mock-leak issue documented at line 218 above.

### Still open (out of scope for this pass)
- Real token streaming end-to-end. Today the pipeline runs to completion then yields the full response as one SSE chunk. The frame shape is OpenAI-compatible, so when we add streaming inside `OpenAICompatibleClient` and thread it through `DirectAnswererAgent`/`SynthesizerAgent`, the frontend won't need changes.
- Function-calling tool loop. `DirectAnswererAgent` currently surfaces `web_search` as an offered tool but doesn't actually execute returned tool calls. Add a tool-call loop in `DirectAnswererAgent.run` once we want the LLM to dispatch search itself.
- Migrating policy review agents to use the orchestration `WebSearchTool` directly (not just the shim). Mechanical work; do it when there's a second consumer that benefits.
- Tavily / SerpAPI providers — `SearchProvider` ABC supports them; add when needed.
