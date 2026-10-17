# UniSensoryAI — Lessons Learned

### Preserve repository line endings when staging partial changes
**Date:** 2026-10-17
**Context:** A generated cached Git patch failed on Windows because subprocess text input converted LF to CRLF before Git compared it with the index.
**Rule:** Read Git blobs as bytes and pass generated patches as UTF-8 bytes to git apply. Inspect each staged diff before committing when a file contains more than one checkpoint topic. Run cached whitespace checks after staging each group, because ordinary unstaged diff checks omit new untracked files.

### Keep test doubles within their real dependency boundary
**Date:** 2026-10-17
**Context:** Checkpoint verification exposed 35 failures because heavy-model mock lists replaced the required PyMuPDF dependency globally, while old converter tests patched convert after the pipeline switched to convert_hybrid.
**Rule:** Mock optional model dependencies without replacing required document parsers during test collection. Use scoped monkeypatches for parser failures and patch the entry point the caller actually invokes. Verify the combined suite, since isolated tests can conceal both collection-order pollution and unused mocks.

### Declare the dependencies exercised by checkpoint verification
**Date:** 2026-10-17
**Context:** New isolated database tests relied on system-installed aiosqlite without declaring it in the development extra. The checkpoint's first test command also selected a runtime-only virtual environment without pytest.
**Rule:** Check test-runner availability before selecting an interpreter and compare imports in new tests with declared development dependencies. Regenerate and verify the lockfile after correcting dependency metadata; a passing system environment alone does not prove a fresh checkout is reproducible.

### Separate development fixtures from the working review queues
**Date:** 2026-10-16
**Context:** Saved synthetic agreements and invoice scenarios cluttered the user's normal review lists, and sample-loading controls could create more dummy records. One PDF-backed agreement had temporary `test` identity fields but contained the user's source data.
**Rule:** Keep example generators and synthetic approval values out of the normal business UI; retain regression fixtures only for isolated development. For user-requested cleanup, verify both synthetic identity and provenance, back up complete dependent history, and validate recovery before committing removal. Never classify a record as dummy from a `test` label alone; preserve real source-linked records, uploads and evidence and verify their fingerprints after cleanup.

### Keep evidence reachable from the field being reviewed
**Date:** 2026-10-16
**Context:** Exact quotes and source references lived below long review forms, forcing repeated scrolling between evidence, original pages and editable values.
**Rule:** Use a shared persistent non-modal inspector with bounded internal scrolling, direct per-field evidence access, every exact page link, and a Back to field action that restores focus and position. Retain all diagnostics and unresolved references behind filters; never treat viewing a warning as acknowledgement. Verify long-form scroll behavior, compact layout, keyboard return and unapplied editor state in the browser.

### Make review transitions visible and scope field citations to their owning document
**Date:** 2026-10-16
**Context:** A read-only extraction exposed Prepare/Load language while the user could not find editing, saving or the agreement repository. Per-field links also risked reusing a primary invoice's citations for supporting documents with identical field paths.
**Rule:** Put Review / edit at the extracted values, open a local draft directly when no unsaved editor exists, and require an explicit replace/keep choice otherwise. Name the saved repository and distinguish unsaved edits, saved versions and approval. Process each handoff once. Aggregate every exact field/child citation, preserve complete-field context on source jumps, and qualify editor shortcuts with the owning document and its own evidence. Never infer a page from an unsupported, ambiguous or foreign citation.

### Preserve model provenance across extraction and document presentation
**Date:** 2026-10-16
**Context:** PAPER retained OCR and business fields but discarded the model identities, while separate frontend fallbacks showed a dash, No model, or Host configured for the same completed upload.
**Rule:** Persist identities from each completed extraction stage, including retries and review calls, through result contracts and queue metadata. Render saved identities through one shared presentation helper. Keep historical missing provenance explicit; never infer it from the current model selector or deployment configuration. Project document metadata once and refresh the shared scoped job cache by exact document identity.

### Verify rendered components after state refactors and serialize builds
**Date:** 2026-10-16
**Context:** A viewer state refactor left a JSX reference to a removed variable, which a production bundle and pure helper tests did not detect. Concurrent frontend builds also raced while clearing the same output directory.
**Rule:** Search all references after renaming state and run undefined-variable plus React-hook checks before live rendering. Verify the actual edited view in the browser. Assign one build owner or separate output directories for concurrent validation.

### Synchronize review semantics and use available width
**Date:** 2026-10-15
**Context:** UI polish left the canonical panel static while only the original PDF changed pages, and short upload controls/history entries still occupied full-width sections.
**Rule:** A side-by-side document review needs one shared page selection driving the original and stored extracted content, with explicit access to complete canonical fields. Match fields through exact document-qualified evidence, show missing page content honestly, preserve mounted editors, and verify compact multi-column layouts with real short and long content.

### Keep hidden review controls reachable
**Date:** 2026-10-15
**Context:** PAPER interface cleanup moved advanced fields into disclosures and source inspection into compact-screen panes. Native form validation and citation navigation still need to reach controls that a reviewer has collapsed or hidden.
**Rule:** Reveal every ancestor disclosure on invalid-field capture before native focus. Reveal a source pane before scheduling its scroll, respect reduced motion, and keep editors mounted across stage changes. Verify these behaviors in the actual compact viewport; never collapse warning counts or bypass explicit review acknowledgements.

### Keep structured monetary prerequisites independent of relaxed legacy fields
**Date:** 2026-10-15
**Context:** Adversarial tests showed a host's relaxed legacy required-field list could let a structured withholding package omit its primary invoice reference, currency or net payable. Whole-unit rounding could also produce withholding larger than a small positive gross amount.
**Rule:** New monetary rules must validate their own semantic minimum inputs and supported sign/bounds before arithmetic or attachment matching. Keep these blockers separate from overridable generic amount findings, even when embedding hosts customize legacy requirements.

### Preserve historical obligations across agreement amendments
**Date:** 2026-10-15
**Context:** Stable installment IDs must survive amendments to prevent repeat billing. Checking every retained installment against the current version's effective interval incorrectly rejected a valid current installment because an earlier obligation was historical.
**Rule:** Validate all obligations against the overall lease interval, then validate the selected obligation against the authoritative version's effective interval. Never reopen an obligation by renaming or dropping saved identifiers.

### Wait for application health before submitting work
**Date:** 2026-10-15
**Context:** Docker reported the API container started while migrations/application startup were still running; an immediate upload probe failed to connect.
**Rule:** Container start is not API readiness. Use a bounded health check before submitting a mutation after restart; retry connection establishment only, and inspect history before repeating an ambiguously accepted request.

### Inspect private extraction artifacts through selected fields
**Date:** 2026-10-15
**Context:** Reading one line of a minified extraction JSON printed the entire private OCR/result artifact. A line count is not an output or privacy bound.
**Rule:** Parse private JSON first, select only necessary nonsensitive keys/counts, and mask account/identity data even when nested inside payment prose. Never print complete model responses, OCR blocks, base64 assets or secret-bearing configuration.

### Verify semantic accuracy separately from evidence coverage
**Date:** 2026-10-15
**Context:** The agreement had 15 missing citations, but source review also found a notary address used as the premises and omitted contingent payment conditions. Stronger schema descriptions alone did not correct the first model rerun.
**Rule:** Reproduce empty/invalid evidence responses, preserve literal source validation, and verify corrected model output against original pages. A quote match establishes traceability only. Test actual source-derived business meanings and keep unresolved OCR/financial ambiguities visible.

### Preserve storage identity when moving manual services into containers
**Date:** 2026-10-15
**Context:** The development Compose file started only databases, published Redis on an already occupied host port, and persisted uploads using host-specific absolute paths.
**Rule:** Inventory actual database endpoints and volume names before changing startup. Preserve project/volume identity, back up records, and compare record/file/settings hashes after migration. Publish only services that host clients need. Resolve legacy upload paths within the configured upload root so Windows and Linux can share existing files without rewriting database rows. Worker fixtures must create real temporary uploads and set `UPLOADS_DIR` while continuing to mock database/model I/O.

### Verify production overlays against the expanded development stack
**Date:** 2026-10-15
**Context:** Adding development API/web services exposed that empty Compose port lists merge rather than remove inherited bindings, while persistent frontend dependency volumes can hide newly built dependencies.
**Rule:** Parse the merged development and production configurations, including inactive profiles when auditing them. Explicitly reset production ports and replace development mounts, select the intended image target, and refresh mounted frontend dependencies from the lockfile on startup. Never print merged secret environment values.

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

### Validate model protocols and business meaning independently
**Date:** 2026-10-15
**Context:** Real scanned-document testing returned an evidence object where the extraction contract required an array. After clarifying the protocol, a schema-valid agreement still selected a notary address as the premises and reversed an AFTER payment condition.
**Rule:** Specify the complete model response envelope and evidence-array item shape in the provider-neutral field protocol. Keep strict validation and traceable quotes. External schemas must distinguish business roles, address roles, monetary bases, and signed deductions without embedding sample answers. Structural validation and exact quotes do not replace semantic review. Preserve untouched model output and warnings separately from manual corrections; never present a reviewed artifact as unassisted model success.

### Inspect extraction artifacts through explicit safe projections
**Date:** 2026-10-15
**Context:** Reading the first lines of a multimodal result printed a very large base64 image because one JSON property occupied a single line.
**Rule:** Parse multimodal result JSON before inspection. Print only selected field values, warning metadata, and counts; never dump image properties, full model payloads, or account identifiers. Save diagnostic responses only in ignored private storage and inspect their structural errors without source values.

### Preserve replacement and editing boundaries in review screens
**Date:** 2026-10-14
**Context:** UI review caught package imports retaining omitted documents from the old package, access refresh discarding unsaved forms, and agreement source IDs being split on commas. Invoice fixtures also initially used the agreement warning-field name.
**Rule:** Replace imported snapshots in full with empty defaults for omitted collections. Keep editors mounted during permission refresh, preserve exact source identifiers, and validate fixture envelopes against actual backend contracts. Mark unapplied structured edits and block form submission until Apply or Discard. Test advisory approval gates while retaining backend authority.

### Inspect storage metadata before defining list ordering
**Date:** 2026-10-14
**Context:** UI planning assumed agreement headers inherited creation timestamps, but only their version snapshots carry those timestamps.
**Rule:** Verify actual ORM columns before defining work-queue ordering. Use a documented deterministic ordering from existing persisted metadata; add a migration only when the business requirement needs a new field. Test latest-version selection, ordering, pagination, and tenant isolation together.

_(Record corrections from failed tests, code review, or bugs here.)_

### Verify the actual server environment before background startup
**Date:** 2026-10-14
**Context:** PAPER tests passed in the system interpreter, but the project's virtual environment lacked `jsonschema` and the background server exited during import. A stdin database check also failed because implicit dotenv discovery requires a script stack.
**Rule:** Inventory declared runtime distributions and import the complete application using the selected server environment before declaring it runnable. Repair missing packages at lockfile versions, then verify a live health endpoint and registered routes after startup. Operational stdin scripts must load `.env` by explicit path, redact secrets, and use bounded database/network checks.

### Validate the complete application schema, including legacy routes
**Date:** 2026-10-14
**Context:** Isolated PAPER routers generated valid schemas, but the full application failed because the legacy HTML preview route used `response_class=None`.
**Rule:** Generate full-application OpenAPI in regression coverage when adding endpoints intended for Swagger. Use a real response class matching the handler's media type. Verify the legacy preview schema along with newly registered business routes; successful health/docs HTML alone does not prove Swagger can load its schema.

### Separate base configuration compatibility from versioned extension policy
**Date:** 2026-10-14
**Context:** The case workflow initially compared a base settings hash to an engine hash that also included injected rule versions, rejecting valid model-independent extensions.
**Rule:** Expose separate base-settings and complete behavior fingerprints. Check dependency configuration compatibility using the former; bind persisted decisions and stale-policy checks to the latter. Test a versioned injected rule through the complete lifecycle.

### Derive result budgets and precision from supported input bounds
**Date:** 2026-10-14
**Context:** A valid 100-document package with host-selected requirements produced more findings than the original 2,000-item assessment cap.
**Rule:** Calculate aggregate output limits from document, field, supporting-type, and extension limits. Bound injected rule outputs and retain all structural findings. Exercise maximum valid packages and exact arithmetic across large and fractional monetary strings; never truncate blockers to fit storage.

### Coordinate shared exports and pytest discovery during parallel changes
**Date:** 2026-10-14
**Context:** Parallel modules overwrote a shared ports export, and identical unit/integration test basenames collided under pytest's import mode.
**Rule:** Assign shared initializers to one owner and merge exports additively. Keep test basenames unique across directories unless explicit package/import configuration supports duplicates. Collect the combined suite before considering isolated subtask tests sufficient.

### Keep executable examples and current status consistent with shipped interfaces
**Date:** 2026-10-14
**Context:** UI examples needed complete revision bodies, wheel smoke checks initially assumed nonexistent export names, and earlier architecture guides still described invoice reconciliation as unimplemented.
**Rule:** Inspect actual exported symbols before composing validation scripts; resolve OpenAPI component references rather than assuming input/output schema names. Exercise complete example files through the real API/service/storage path and validate documentation bodies. Label historical assessments separately from current follow-up status; update linked guides and migration heads when a phase ships.

### Select superseding authority before checking expiry
**Date:** 2026-10-14
**Context:** Filtering approved agreement versions by both start and end date before choosing the latest version revived older terms after a shortened amendment expired.
**Rule:** Select the highest approved revision whose start has occurred, then verify that selected revision's end date. Test dates before, within, and after the amendment, plus newer drafts and future approvals.

### Separate extraction validity from approval completeness
**Date:** 2026-10-14
**Context:** Nullable extraction contracts initially allowed publication without currency or rent-specific payment terms. Retained warnings needed a recorded acknowledgement, and a configured required extensions dictionary could be empty.
**Rule:** Keep unknown source fields valid in drafts, then apply host-owned publication requirements, including conditional fields and empty collections, before approving. Preserve extraction warnings and explicitly record their acceptance; never equate schema-valid output with an approved business decision.

### Protect historical identity and real transaction behavior
**Date:** 2026-10-14
**Context:** Agreement snapshots materialize canonical identity from a shared header, so editing that header would alter historical meaning. SQLite's legacy transaction mode also let a savepoint complete outside the intended outer rollback.
**Rule:** Guard stable header identity as well as immutable snapshots and approvals. Database integration fixtures must establish a real outer transaction before savepoints and prove caller rollback, tenant-qualified foreign keys, uniqueness, and stale revision/approval behavior. Keep real database fixtures separate from mocked unit tests.

### Confirm verification paths and typed factories against the actual source
**Date:** 2026-10-14
**Context:** Final formatting referenced an assumed integration-test filename, and an unannotated settings default factory widened literal-key types during strict checking. Schema test setup also initially assumed unsupported content fields.
**Rule:** Inventory files before composing verification commands, construct fixtures from actual typed contracts, and annotate factories whose inferred types differ from public model fields. Demonstrate test failures for behavior changes, then rerun only the checks affected by the correction.

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

### Keep citation completion from rewriting extracted values
**Date:** 2026-10-15
**Context:** Literal citation spans started mid-word and duplicated arbitrary fragments when automatically copied into payment and other narrative terms, losing important amounts and conditions despite passing exact-match verification.
**Rule:** Freeze canonical values during evidence completion. Keep exact source quotes separate from narrative candidates, mark narratives for source review, and verify condition-level completeness against original pages. A literal quote match proves traceability, not semantic accuracy or completeness.

### Validate the completeness of focused model responses
**Date:** 2026-10-15
**Context:** Focused field extraction accepted an empty or extensions-only result under a relaxed full schema, so requested fields bypassed configured retries. Original-page checks caught a missing currency.
**Rule:** Validate focused output against its projected schema as well as the full partial contract. Require every requested key, allow explicit null only where valid, retry omissions within the existing bound, and preserve original candidates plus review gaps when retries are exhausted.

### Keep failed live acceptance distinct from passing pipeline tests
**Date:** 2026-10-15
**Context:** After citation/retry tests passed, a live agreement rerun had zero missing citations but selected the tenant as landlord and omitted contractual prerequisites.
**Rule:** Preserve and report failed original-source acceptance checks. Do not repeat models until a favorable sample appears or label manually corrected output as unassisted extraction. Provide separately labelled source-reviewed drafts with explicit remaining unknowns and keep approval a human decision.

### Bind persisted extraction to resource ownership and host scope
**Date:** 2026-10-15
**Context:** Review caught orphan originals/artifacts on queue or database failure, a postcommit Redis cleanup path that could retry completed output, host-specific PAPER calls ignoring the selected backend, and UI uploads missing from shared history until reload.
**Rule:** Model submission/commit ownership explicitly; discard only proven-uncommitted creator-owned files and preserve uncertain commits. Keep postcommit housekeeping outside processing failure paths. Bind the complete UI API surface and source links to the selected host, refresh shared server history after accepted background work, and keep credentials out of all public history serializers and browser storage.

### Separate full-document OCR budgets from per-call limits
**Date:** 2026-10-15
**Context:** The 38-page scanned sample exceeded the reusable service's five-minute document budget despite valid PDF normalization; automatic queue retries repeated that timeout.
**Rule:** Inject validated host-owned workflow budgets for long queued PDFs while preserving model-call deadlines and library defaults. Verify actual multi-page completion, retain partial output and evidence warnings, and never equate successful processing with verified accounting facts.

### Verify the actual in-app viewport before finishing UI changes
**Date:** 2026-10-15
**Context:** Desktop screenshots alone hid the existing fixed sidebar consuming most of a 347px in-app browser. The PDF workflow was technically present but difficult to use.
**Rule:** Inspect the user's current viewport, preserve accessible navigation in compact layouts, and check both narrow and desktop page widths for overflow. Reset temporary viewport overrides after responsive validation.

### Bound intrinsic workflow grid widths
**Date:** 2026-10-15
**Context:** A saved invoice workspace expanded to 389px inside a 355px viewport because stacked grid tracks inherited disclosure-summary min-content widths.
**Rule:** Use explicit shrinkable grid tracks and min-width: 0 on workflow children and controls. Allow summaries and long identifiers to wrap. Measure both saved and editor views in the actual viewport; do not conceal layout errors with overflow hiding.

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
