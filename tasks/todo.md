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
