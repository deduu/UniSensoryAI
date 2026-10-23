# UniSensoryAI — Lessons Learned

### Preserve evidence while generalizing private review notes
**Date:** 2026-10-23
**Context:** Checkpoint publication review found private source details in newly accumulated walkthrough notes. A broad paragraph replacement also removed an original UI warning count that was unavailable afterward.
**Rule:** Keep an exact local before-image, match complete replacement anchors and suffixes, and compare every retained count and validation statement before saving. Generalize private names, locations, identifiers and amounts without changing technical findings or acceptance limits. If evidence cannot be recovered, omit the unsupported number and retain only verified wording.

### Verify checkpoint types against locked dependencies
**Date:** 2026-10-23
**Context:** Unpinned verification tools selected a newer SQLAlchemy API than the application lockfile and produced unrelated generic-type errors. The locked mypy version also exposed missing annotations in new metadata, scalar validation and selected-version code.
**Rule:** Use the lockfile's tool and runtime versions for checkpoint checks. Annotate validation adapters and deserialized values, and pass already-validated contract fields into typed constructors. Treat the installed Alembic distribution as third-party in migration integration checks when the local migration directory confuses import classification.

### Include new regression modules in checkpoint lint checks
**Date:** 2026-10-23
**Context:** Checkpoint lint found a new source-lookup test importing AsyncIterator from typing despite the repository's collections.abc convention.
**Rule:** Include new test files as well as application modules in scoped lint checks, and import runtime collection protocols from collections.abc when supported by the minimum Python version.

### Complete source tax components without inventing accounting authority
**Date:** 2026-10-23
**Context:** The invoice retained its printed PPh deduction only as a legacy signed tax amount, leaving the typed withholding component empty. Recording the supported component exposed missing VAT, withholding evidence and approved rate/rounding policy. The contract stated the whole lease and installment payment dates but no per-installment coverage dates.
**Rule:** Record each explicitly printed component with page evidence and preserve printed monetary values. Reassess honestly even when accurate completion adds findings. Never infer zero VAT, rounding, approved tax policy or installment service coverage from omitted text, percentage labels, payment dates or the full lease term. Preserve originals and immutable history and reconfirm associations after source corrections.

### Separate visible value equality from reconciliation authority
**Date:** 2026-10-23
**Context:** A saved invoice with missing service dates had no assessed agreement reference. The comparison gave every row the same coverage warning, hiding equal currency/account values and more specific saved findings. Linked IDs also looked like extracted identifiers under generic Vendor/Store labels.
**Rule:** Show simple literal value comparison separately from the saved assessment and preserve blocking findings ahead of unavailable-authority fallbacks. Label assigned IDs explicitly, never substitute them for missing source fields, and leave amount, tax and coverage calculations to the engine. Clone nested test fixtures before introducing mutation-based scenarios so one regression cannot contaminate later tests.

### Preserve inherited policy semantics in settings editors
**Date:** 2026-10-20
**Context:** A field requirement editor initially serialized every effective field as an explicit override. The engine gives explicit required tax fields additional document-presence meaning, so an unrelated invoice edit could require a tax document or disable an approved substitution.
**Rule:** Keep inherited defaults distinct from saved overrides across the catalog, editor and update contract. Verify read-edit-save behavior against the actual readiness and reconciliation engines, including optional document roles and approved substitution paths; equal displayed labels do not guarantee equal policy behavior.

### Keep failed new validation distinct from legacy data
**Date:** 2026-10-17
**Context:** A role-policy load failure initially retained new agreement fields without party metadata, allowing them to resemble historical versions exempt from new review requirements. A focused worker regression exposed this path.
**Rule:** Stamp unresolved metadata and safe diagnostics on new validation failures; preserve the exemption only for genuine historical snapshots. Test configuration failure, cancellation and later metadata removal. Keep source-reviewed corrections separate from unchanged automatic output, and never cite protocol constants as document facts.

### Validate legal party roles across the complete representation chain
**Date:** 2026-10-17
**Context:** The current agreement extraction selects the tenant as `vendor_name` and cites a literal tenant-representation clause. The schema already defines vendor as landlord, but structural and quote-occurrence validation still accept that wrong role. The landlord name, representative and role definition span different PDF pages. Raw OCR Markdown also appears literally in the review UI.
**Rule:** Extract principals, representatives and explicit roles separately, retaining all role-defining page citations before mapping a supplier name. Treat source located, role verified and reviewer confirmed as separate states. A generic same-model recheck or citation repair does not establish semantic accuracy. Preserve raw text and evidence; improve their reading presentation without rewriting source strings. Correct approved data through a new reviewed version and test multipage roles, swapped party order and an exactly cited wrong party.

### Keep reviewed contract association separate from source extraction
**Date:** 2026-10-17
**Context:** The old identity shortcut copied master IDs into document fields, making reviewer-assigned routing values look source-derived. Initial association integration also discarded the inspected schedule when an invoice edit correctly invalidated confirmation.
**Rule:** Preserve extracted fields and evidence when assigning canonical IDs. Bind confirmation to the exact approved version and source/allocation content, stamp provenance on the server, and reject stale bindings. Invalidate confirmation after edits while retaining a clearly labelled candidate preview so the reviewer can finish installment/allocation work. Omit absent new fields from historical fingerprints and verify legacy approval behavior.

### Keep comparison expectations within the server's supported billing path
**Date:** 2026-10-17
**Context:** Review found that an invoice with a missing installment selection could show annual fixed rent as its expected cash amount, although the backend deliberately delegates all scheduled pricing to the installment rule.
**Rule:** Show the selected approved installment or an unknown expectation; never substitute another pricing basis. Bind presentation to the exact approved version, retain saved findings, and distinguish no reported finding from a positive evaluated check. Cover absent and invalid selections before marking a comparison complete.

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

### Use ripgrep filters for portable file selection
**Date:** 2026-10-17
**Context:** A deployment audit passed `tests/unit/test*` as a path to ripgrep under PowerShell; the literal wildcard was rejected before any search ran.
**Rule:** Pass existing directory roots to `rg` and use `-g` for filename patterns. Verify the corrected search succeeds before treating an empty result as evidence that a capability is absent. When counting optional arrays in PowerShell configuration checks, filter null entries before using `@(...).Count` so an absent property is not reported as one item.

### Verify permissions and audience behavior for authenticated demos
**Date:** 2026-10-17
**Context:** Deployment inspection showed that successful OAuth login creates a personal tenant with a `member` role, while PAPER decisions require an allowed persisted role. Official Google documentation also exempts basic identity scopes from the testing-mode test-user restriction.
**Rule:** Check business permissions and tenant ownership after login before declaring a full demo ready. Assign only the intended reviewer's required role and prepare documents in the presenting account. Verify provider audience restrictions for the exact scopes; do not assume login or OAuth testing mode creates an email allowlist.

### Check current certificate capabilities before requiring a domain
**Date:** 2026-10-17
**Context:** The initial public HTTPS guide assumed domain ownership and OAuth. The user wanted a shared temporary demo; current Let’s Encrypt IP certificates and an authenticated same-origin gateway remove those setup steps.
**Rule:** Confirm the user's desired audience and login model before adding hosting dependencies. Check current CA/client support for trusted public-IP certificates, require automatic renewal, and guard both frontend and API when using a shared application context. Do not equate disabled application OAuth with an unprotected public gateway.

### Keep provider endpoint settings visible in deployment examples
**Date:** 2026-10-17
**Context:** The demo guide mentioned `OPENAI_API_BASE` only in prose while its copyable environment block pinned PAPER to the official endpoint. This obscured the existing custom-provider setting and its extraction override.
**Rule:** Include both chat and extraction endpoint variables in full-app examples. Explain fallback precedence and preserve the user's tested provider URL; label official endpoints as examples rather than silently replacing custom configuration.

### Separate retained diagnostics from current review requirements
**Date:** 2026-10-17
**Context:** Agreement v5 carried 49 extraction diagnostics even after citation repairs and a party correction. The UI presented all 49 as current warnings; all 23 rejected-citation paths had traceable current evidence, while several narrative summaries still changed operative conditions.
**Rule:** Preserve the original diagnostic log and compute current presentation separately. Recheck exact field/document/source text before labelling a rejected citation historical; keep semantic, incomplete-field and unknown issues active. Do not equate a matching quote with a correct value or complete clause. Reopen citation review after edits and label extraction list counts as retained log entries. Retain explicit approval acknowledgements and never rewrite historical versions to improve a count.

### Do not reuse preview serializers for document result state
**Date:** 2026-05-08
**Context:** `GET /v1/jobs` truncated `content_text` to 500 characters for list previews, but the
frontend reused that job payload as the source of truth for extracted document content.
**Rule:** Keep previews in dedicated fields or UI-only derivations. API fields named like persisted
results (`content_text`) must carry the full durable value.

### Project private historical metadata into strict public contracts
**Date:** 2026-10-17
**Context:** Adding typed extraction provenance caused history reads to reject older private `document_reuse.purpose` annotations, producing a list failure despite valid source identity and SHA256.
**Rule:** Test stored legacy metadata before exposing a new strict response contract. Whitelist the public projection at the read boundary, validate all required public values, retain strict direct inputs, and leave persisted history untouched. Compare refreshed database timestamps when SQLite normalizes timezone representation.

## Extraction usage accounting — 2026-10-17

- Capture usage at the model boundary before output validation; rejected, truncated and refused responses can still consume tokens. Include OCR, selection, review, repair and retry calls in one async-context-scoped ledger, never a shared current-job variable.
- Keep unknown counters and missing prices explicit. Preserve immutable per-call counters and decimal pricing snapshots; do not reconstruct historical tokens from characters or label a public-price estimate as the actual provider bill.
- Bind prices to the configured model and the reported response model. Deployment aliases require explicit approved response-model aliases; an unrecognized returned model must remain unpriced. Compatibility adapters must retain actual model identity and nested cached-token counters too.
- Carry the typed ledger through artifact/document persistence errors, graceful cancellation, worker recovery and retry backoff. Persist before a delay; a repeated attempt of the same job must resume prior counters rather than overwrite them. Abrupt process/storage loss cannot be represented as complete metering without a durable event sink.
- On this Windows host, the sandboxed asyncio runner can stall. Use the approved host Python runner for isolated mocked tests, and point cached mypy at that Python executable so installed application dependencies are resolved.

### Clause fidelity and source selection
- Narrative paraphrases can change the legal actor, AND/OR alternatives, prerequisites, notice triggers, or remedies while retaining literal but insufficient citations. Opt annotated narrative fields into exact source-paragraph selection, inspect adjacent paragraphs and continuation pages, and keep human semantic coverage review open; copied text establishes fidelity, not completeness or legal interpretation.
- Confirm apparent OCR/name spelling differences with a magnified crop of the original PDF before proposing a correction. A low-resolution visual reading is not enough to override a retained literal quote; preserve the quote and record any real visual correction separately.
### Make document review readable and keep policy provenance honest
**Date:** 2026-10-18
**Context:** All-fields agreement review exposed long disabled editors and JSON, while approval labels implied that reviewer-entered policy references selected executable rules.
**Rule:** Render saved terms as semantic values with full clauses and nested source links. Keep the PDF, current field value and retained quote accessible together; use bounded desktop panes and section navigation. Native clause edits must retain exact strings, ordering and null/empty distinctions, and pending advanced JSON must block competing edits and submission. Keep required policy references explicit, explain whether they are verified against a catalog, and never fill them from unrelated invoice matching configuration. Verify compact behavior after responsive transitions settle and reset viewport overrides.

### Format money without changing its meaning or interrupting selection
**Date:** 2026-10-18
**Context:** Monetary inputs and nested schedules exposed raw digits. Live verification caught a focus-time value rewrite racing select-all/paste; component tests also caught a native validity message persisting after a synchronous parent update.
**Rule:** Format exact decimal strings by explicit schema semantics and the owning document/schedule currency, never by numeric-looking text or floating-point conversion. Preserve fractional scale, unknown values, raw JSON, rates, IDs and original quotations. Keep focus and typing from rewriting the display; format on blur, validate locale grouping strictly and retain invalid local text without applying it. Reconcile native custom validity after each render, and keep guidance separate from stable accessible input names. Test grouped replacement, values above the safe-integer range, currency changes and invalid-input submission gates in the actual UI; cancel local verification drafts.

### Keep assigned identity, source extraction and billing authority distinct
**Date:** 2026-10-18
**Context:** The real agreement could not publish because source store_id was null although its validated master identity had a store ID. Missing invoice coverage then hid the confirmed contract from comparison entirely. Verbose diagnostics also obscured which fields were actually absent.
**Rule:** Check required assigned identifiers at the canonical identity boundary; reject contradictory source identifiers without filling absent source values. Missing extracted IDs do not mean the master assignment is missing. A server-confirmed selected approved contract may locate reference values and PDFs while billing coverage is unknown, but must never establish assessed authority, a clean match or payment eligibility. Preserve authority-reference precedence and exact version/tenant/identity checks. Present unresolved diagnostics by field with concise reason/action, separate missing from present-but-unverified values, and retain exact messages and source pages under Details. Historical diagnostics are not a list of certified successful extractions.

### Preserve UTF-8 when editing on Windows
**Date:** 2026-10-18
**Context:** Piping a Python edit script through PowerShell changed a Unicode separator to an invalid byte, and newline translation introduced CRCRLF.
**Rule:** Prefer apply_patch for Unicode source edits. For scripted edits, keep command source ASCII, read/write explicit UTF-8 and set newline='\n'; verify decoding and git diff --check before UI/build verification.

### Preserve intent, local work and exact saved versions across workspace navigation
**Date:** 2026-10-18
**Context:** Combining source review, agreement review and reconciliation introduced competing deferred navigation requests. Effect cleanup could invalidate an already-consumed request during StrictMode replay and leave a loading state stuck.
**Rule:** Keep editors mounted across view changes and reset them only at account/backend boundaries. Use a shared monotonic intent sequence for saved-record and extraction handoffs, invalidate pending source navigation on newer navigation, and require keep/replace before discarding local work. Resolve exact requested versions independently from latest-history eligibility; never substitute the latest version after an exact lookup fails. Cleanup should guard unmounted updates without invalidating the sole consumed request unless it will be restarted. Verify imports with the production bundle as well as component tests; server rendering alone may not expose a missing ESM export.

### Unknown legacy source identity does not mean no saved workflow
**Date:** 2026-10-18
**Context:** Completed older extraction jobs lacked meta.document_id even though their retained artifacts and saved cases used the same canonical source. A new document index therefore initially missed their saved workflow links.
**Rule:** Distinguish unresolved source indexing from a verified absence of saved records. Repair only validated, tenant-owned bounded artifacts with a dry-run first, add the canonical source ID without rewriting source data or chronology, and compare complete saved-history fingerprints afterward. Preserve archived attempts and explicitly choose among multiple source-linked masters instead of guessing by filename or taking the first match.

### Separate saved source review, case selection and reconciliation readiness
**Date:** 2026-10-18
**Context:** Invoice review exposed Reconcile package before users had saved/reviewed individual documents or chosen the sources belonging to a case.
**Rule:** Save incomplete source drafts independently of master assignment and assessment. Append immutable reviewed versions with server-stamped reviewer/time; corrections require fresh review. Resolve exact tenant-owned reviewed snapshots when assembling a case, reject duplicate source IDs even under different draft IDs, and never trust caller-written review provenance on manual imports. Check readiness without writing history, then recheck current authority on explicit reconciliation in the host transaction. Requirement labels must describe actual engine guards: optional presence never certifies a skipped accounting check or waives coverage, installments, withholding or AP authorization. Keep duplicate diagnostics in history while presenting one actionable prerequisite. Async attachment lookup must merge into the current contract/allocation package rather than an older closure.
