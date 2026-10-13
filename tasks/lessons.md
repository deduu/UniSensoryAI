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

### Keep namespace and stub discovery consistent during isolated type checks
**Date:** 2026-10-13
**Context:** Publication verification initially mapped extraction files to two module names; pointing an isolated mypy tool at the system interpreter then bypassed the stubs installed in the tool environment.
**Rule:** Use explicit package bases for the repository's `src` namespace. Run mypy in the same environment as its injected dependency stubs; choose `--python-executable` only when that interpreter also provides the intended stubs. Distinguish checker setup errors from application type errors.

### Verify physical resource and external serialization boundaries
**Date:** 2026-10-13
**Context:** Extraction integration review caught rotated image crops using mismatched coordinates, shared MuPDF table buffers accessed concurrently, configurable request budgets bypassing server ceilings, early cleanup failures skipping later providers, YAML paths forwarded as strings, and Pydantic aliases/CLI diagnostic output breaking external serialization.
**Rule:** Normalize render and source coordinates explicitly and test pixel content on rotated pages. Protect process-global parser state across instances, retain physical inference leases after caller cancellation, apply host-owned API budgets, and close every owned resource even after one failure. Verify public configuration and serialization with real embedding/CLI/API tests, preserve caller schema keys, and keep diagnostics separate from machine-readable stdout.

### Preserve JSON Schema keyword semantics and provenance during extraction
**Date:** 2026-10-13
**Context:** Schema review found that recursively deleting every `required` key would corrupt business properties and literal values, and that unresolved references, empty evidence quotes, or chained validation exceptions could undermine the advertised boundary.
**Rule:** Traverse schema positions rather than arbitrary JSON; validate references before execution; reject empty or unsupported evidence; sanitize error causes that contain source values. Validate assembled data against the unchanged external schema and state limits of partial validation for conditional or negated schemas.

### Verify boundary fixtures against actual limits and supported Python versions
**Date:** 2026-10-13
**Context:** A chunking test fixture fit within the model's declared context, so it never exercised the intended boundary. Review also caught Python 3.11-only Self imports in code supporting 3.10 and Pydantic's reserved schema attribute.
**Rule:** Construct boundary tests that demonstrably cross the actual serialized request budget; keep runtime annotations compatible with the package's minimum Python version and avoid reserved model field/test fixture names.

### Bind provenance and resource ownership explicitly in workflow designs
**Date:** 2026-10-11
**Context:** Architecture review found that the invoice example promised source chunk citations but supplied only text to the capability. Generated image references also needed a shared resolver and lifetime contract, and optional analysis needed diagnostic persistence before API exposure.
**Rule:** Trace every output's evidence and binary reference back to an explicit input or injected service. Specify asset ownership and cleanup, preserve task cancellation, and persist derived results and failure diagnostics before wiring an optional workflow into user-facing endpoints.

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
7. Confirm that the selected Python interpreter includes pytest before running verification; an existing .venv alone does not establish that development dependencies are installed.

### Verify the test environment before selecting an interpreter
**Date:** 2026-10-11
**Context:** Architecture walkthrough verification selected the existing `.venv` interpreter, but pytest was installed only in the system interpreter. Async workflow runs then stalled even with plugin autoload disabled.
**Rule:** Check the interpreter's test dependencies first. If an async verification run stalls without results, bound and stop it, report the limitation, and distinguish inspected contracts from successfully executed tests.

### Distinguish sandbox failures from application failures
**Date:** 2026-10-11
**Context:** The checkpoint frontend build failed with EPERM resolving `index.html` in the sandbox, and earlier async tests stalled. Authorized bounded retries outside the sandbox passed the build and 81 focused workflow/auth tests.
**Rule:** When filesystem permissions or the execution sandbox block validation, retry the same bounded check with authorized escalation before attributing the failure to application code. Report the environment and retain the distinction between focused checks and full-suite verification.

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
