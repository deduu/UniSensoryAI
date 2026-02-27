# UniSensoryAI — Lessons Learned

## Patterns

### Always thread configuration through function parameters
**Date:** 2026-02-26
**Context:** `process_document_job()` hardcoded `model_id = "qwen2-vl-2b-instruct"` instead of
accepting it as a parameter. The API stored model_id in job metadata but the processor ignored it.
**Rule:** Never hardcode config values inside functions. Accept them as parameters with sensible
defaults. Let the caller (queue worker) extract from metadata and pass through.

### Update type hints when changing function signatures
**Date:** 2026-02-26
**Context:** Changing `process_document_job(file_path)` to `process_document_job(file_path, model_id)`
required updating `Callable[[str], Awaitable[Any]]` → `Callable[[str, str], Awaitable[Any]]` in
queue_manager.py and init_ingestion_queue.
**Rule:** When modifying a function signature, grep for all `Callable` type hints referencing it.

## Corrections

_(Record corrections from failed tests, code review, or bugs here.)_

## Rules

1. Config values flow as parameters, not hardcoded constants
2. Type hints must match actual function signatures (especially Callable types)
3. Tests should cover both the happy path and the default fallback behavior
4. Mock DB sessions in unit tests — never hit real database
5. Mock model inference — never load real models in unit tests
