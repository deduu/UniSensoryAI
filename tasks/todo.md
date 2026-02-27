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
