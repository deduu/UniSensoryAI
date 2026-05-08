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

### Check installed component API versions before passing styling props
**Date:** 2026-05-07
**Context:** `react-markdown` v10 throws when given `className` directly. Styling must be applied
to a wrapper element or through supported component overrides.
**Rule:** For third-party React components, verify the installed major version's supported props
before using examples from older versions.

## Rules

1. Config values flow as parameters, not hardcoded constants
2. Type hints must match actual function signatures (especially Callable types)
3. Tests should cover both the happy path and the default fallback behavior
4. Mock DB sessions in unit tests — never hit real database
5. Mock model inference — never load real models in unit tests
6. Verify installed third-party UI component APIs before using version-sensitive props

### Preserve source extraction before enrichment
**Date:** 2026-05-07
**Context:** DOCX extraction was sent through a "key information" model prompt, so saved
`content_text` became a short summary instead of the full converted document text.
**Rule:** For Office/text converters, persist the converted source text as the extraction output.
Run model enrichment as a separate field or workflow when summaries/insights are needed.

### Persist derived analysis before returning UI results
**Date:** 2026-05-08
**Context:** Policy review results were returned from `POST /policy-review` but were lost when the
user navigated away because no durable field stored the review output.
**Rule:** Any user-triggered analysis that appears as a reusable document result must be persisted
before returning the API response, and job/document serializers must expose that saved result.

### Do not reuse preview serializers for document result state
**Date:** 2026-05-08
**Context:** `GET /v1/jobs` truncated `content_text` to 500 characters for list previews, but the
frontend reused that job payload as the source of truth for extracted document content.
**Rule:** Keep previews in dedicated fields or UI-only derivations. API fields named like persisted
results (`content_text`) must carry the full durable value.
