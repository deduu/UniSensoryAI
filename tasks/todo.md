## Publish PAPER development checkpoint — 2026-10-17

- [x] Inspect repository instructions, accumulated changes and existing branch history.
- [x] Review focused commit boundaries and exclude private, generated and local configuration artifacts.
- [x] Run backend, frontend and deployment checks; document any existing limitations.
- [x] Create focused checkpoint commits and inspect staged content for each commit.
- [x] Push the checkpoint branch and verify the remote commit matches local HEAD.

### Plan and scope

Publish the accumulated implementation on `codex/reusable-pdf-extraction` as several focused commits. Review extraction, PAPER domain/persistence/API, frontend, deployment and documentation changes with read-only parallel help. Preserve private uploads/results and local runtime configuration; do not change business records or run model inference. Plan mode and TodoWrite are unavailable in this session, so this checklist and the initial commentary provide the planning check-in. The user's checkpoint request authorizes creating and pushing the commits.

### Review

- Reviewed the accumulated work and selected seven commits: parser test isolation, generic extraction reliability/provenance, PAPER domain/persistence/reconciliation, durable queued extraction/API integration, frontend review/history, deployment, and documentation. The extraction deployment YAML contains only environment placeholders and is included; synthetic developer fixtures and the synthetic UI screenshot are publishable. Added `tmp/` to ignore the generated local image. Existing ignored uploads, results, environment credentials and recovery exports stay local.
- Declared the missing `aiosqlite` development dependency and regenerated the lockfile. Offline lock verification passes, and Alembic reports the single head `dc728f04a912`. No migrations or business-record changes were executed for publication.
- The first combined backend run exposed 35 failures from global PyMuPDF mocks and stale converter test patches. Removed required PDF parsers from optional-model mock lists and updated tests to patch the actual `convert_hybrid` entry point. The focused mixed API/real-PDF regression run passed 82 tests. The final full suite passed **984 tests**, with **86%** coverage and five existing mock/JWT test warnings; HTML coverage remains ignored. Sandboxed async runs stalled, so successful Python verification used authorized execution outside the sandbox.
- All **69 frontend tests** and the production Vite build pass. Explicit JSX, undefined-variable and React-hook checks have zero errors and one ref-cleanup warning. Development, production with all profiles, and GPU Compose configurations validate; production hostname/email variables are unset locally, as expected. Existing Browserslist age and bundle-size advisories remain.
- All **115 new Python files** pass Ruff and Black/isort checks. Strict mypy passes for **70 changed extraction/new PAPER source files**. Broader lint/type checks expose existing-pattern debt in legacy API/model-export/test modules and the unchanged PDF reader's third-party typing annotations; the standard frontend lint script also lacks an ESLint configuration. These checks are reported separately from the passing scoped checks. SQLite integration tests do not establish PostgreSQL concurrency behavior.
- Converted machine-specific documentation links to portable repository references and aligned README review/edit wording with the UI. The final index audit covered 232 changed paths (about 1.95 MB), finding no private/generated paths, oversized artifacts or credential signatures. Cached and cumulative whitespace checks pass.
- Published the six implementation commits through `4962b41` to `origin/codex/reusable-pdf-extraction`, established branch tracking, and verified the remote hash equals local HEAD. This seventh documentation commit records the verified publication and validation results before the final push. Main was not updated.

## Remove PAPER dummy examples — 2026-10-16

- [x] Inventory saved demo records and confirm ownership/dependencies without exposing private contents.
- [x] Export an exact local recovery backup, remove only verified synthetic PAPER records in one transaction, and verify real data is unchanged.
- [x] Remove web sample/scenario/approval-prefill controls while preserving empty manual forms, extraction review and developer regression fixtures.
- [x] Verify lists and ordinary UI flows, run frontend checks/build, and update documentation and lessons.

### Plan and scope

The screenshot identifies saved DEMO invoice cases. Inspect the local development tenant's agreements, case versions, decisions and duplicate claims; include only records whose synthetic identity/provenance is verified. Keep an ignored local recovery export before cleanup, validate dependent references, and fingerprint retained rows and source files. Preserve real PDF uploads/extractions and test fixtures in source control. Remove production-facing example creation controls so the lists remain clear. Root owns database cleanup and final verification; delegated frontend work follows AGENTS.md. Plan mode/TodoWrite are unavailable; this checklist and initial commentary serve as the planning check-in.

### Review

- Confirmed four generated DEMO agreement identities and all seven saved DEMO invoice cases, using synthetic source IDs/reasons as well as identity prefixes. Preserved the additional agreement 65 (four versions and one approval), because it references the user's original PDF even though its vendor/store identifiers are `test`.
- Exported 42 dependent rows to ignored data/runtime/paper-demo-backup-20261016T165543344938Z.json before mutation: four agreements, five agreement versions, four approvals, seven invoice cases, nine invoice versions, five AP decisions and eight duplicate claims. Removed those rows in one serializable local database transaction, with tenant/identity/provenance/reference guards. Proved recovery by restoring the backup inside a savepoint, verifying the original full PAPER snapshot, then rolling back that savepoint before committing cleanup. Recovery instructions and an adjacent result report are retained locally.
- Fingerprinted all retained PAPER rows, seven unrelated database tables and all 19 uploaded source/result files. They match after cleanup and again after browser QA. No real upload, source evidence, real agreement history, account or reviewer permission was removed or edited.
- Removed production-facing agreement/monthly/installment loaders, invoice scenario helpers, synthetic invoice-to-tax copying and approval autofill. New draft now always opens an empty agreement; New invoice package retains optional selected identity but starts document fields empty. Manual forms, extraction handoffs, typed JSON import, blank withholding-certificate entry, validation, reconciliation and approval handlers remain. Developer JSON fixtures and automated tests stay isolated from the web UI.
- All 69 frontend tests, focused JSX/hooks/undefined-variable lint, the production build and whitespace checks pass. Existing Browserslist age and large-bundle advisories remain. Live UI confirms no demo case rows or sample controls, a single preserved agreement labelled 65, blank new agreement/invoice fields, and a blank withholding entry without fabricated amounts or source IDs. Temporary local forms were cancelled without saving. The 355px layout has no horizontal overflow; screenshot retained in ignored data/runtime/paper-real-sample/paper-demo-cleanup-ui.png. Updated the UI guide and lessons.

## Integrated document review evidence inspector — 2026-10-16

- [x] Design always-accessible evidence, warnings and source references without a long footer or lost editor position.
- [x] Write failing regressions for field/page/search filtering, retaining exact and unresolved citations without mutating source data.
- [x] Add a shared persistent review dock with contextual field evidence, multi-page source navigation and return-to-field access.
- [x] Integrate agreement source review and preserve manual, invoice and approval workflows, unsaved editors and document identity checks.
- [x] Verify desktop/compact accessibility, scroll behavior, frontend tests/build, and update documentation and lessons.

### Plan and scope

Replace the bottom-of-document evidence disclosures and duplicated agreement Source review footer with one shared review inspector. Keep a compact dock accessible while scrolling, opening a bounded non-modal panel for evidence, warnings or source references. A field source shortcut will reveal its citations alongside the original, retain all linked pages and provide Back to field. Support all/page and text filtering without guessing missing links. Preserve mounted editors, native validation, document-qualified evidence, warning visibility and separate save/approval actions. No model, API, extraction rerun or business-record changes are needed. Plan mode/TodoWrite are unavailable; this written plan and commentary provide the planning check-in. Use focused parallel help under AGENTS.md; root owns integration, build and browser verification.

### Review

- Replaced the inline warning/evidence footer and duplicate saved-agreement Source review footer with a shared persistent Review tools dock. Its Evidence, Warnings and Sources panels are non-modal, bounded and independently scrollable, including on compact screens. Saved agreements retain exact JSON separately and reserve space below controls for the dock.
- Per-field Evidence opens exact and descendant quotations in place. Page shortcuts reveal the PDF with the same field evidence, retaining every linked page. Back to field restores the mounted complete-field editor, focus, disclosure and position. Escape/close returns keyboard focus to the toolbar. Search/current-page filters retain original items and keep unlinked sources explicit; viewing warnings never acknowledges them for approval.
- The helper tests failed on the missing new export before implementation. All 69 frontend tests, scoped JSX/hooks/undefined-variable lint, final production build and whitespace checks pass. Existing Browserslist age and large-bundle advisories remain. No backend/model/schema or business-rule changes were made.
- Live browser checks at 1440×1000 and the normal 355×884 viewport verified persistent positioning while scrolling, no horizontal page overflow, multi-page payment evidence (pages 9 and 10), exact-page filtering, an empty search state, all 42 retained unique agreement warnings and source references, missing rent-type evidence without a guessed page, Escape focus return, and Back to field. Scalar draft edits and unapplied JSON survived evidence/page round trips; temporary test edits were restored.
- Invoice review exposes all nine retained citations to page 1. Stage switches show only one active dock and keep both local editors mounted. No agreement/invoice was saved, approved, reconciled, uploaded or re-extracted in this task. The existing explicit warning acknowledgement remains in the approval form. The final viewport override is reset; screenshots are retained in ignored data/runtime/paper-real-sample/paper-evidence-inspector-{desktop,compact}.png. The usage guide and lessons now describe the inspector.
## PAPER review actions, repository navigation and field source shortcuts — 2026-10-16

- [x] Trace extraction-to-draft handoff and make Review / edit, Save draft version, and Rent Agreement Master Repository discoverable.
- [x] Add test-first exact field-to-page projection covering multiple citations, nested fields and unresolved/foreign evidence.
- [x] Add accessible source shortcuts beside extracted and editable fields; preserve complete-field context and unsaved edits when jumping to a source.
- [x] Verify existing flows, overwrite protection and approval gates with frontend checks and live desktop/compact browser testing.
- [x] Update the user testing guide and capture verification results and lessons.

### Plan and scope

The current Prepare / Load handoff makes a read-only extraction look like the end of the workflow. Use an explicit Review / edit action to open a local editor directly when no unsaved editor exists, retaining explicit replacement choice if one does. Label the master repository in navigation and the workspace, show save controls near the editor entry, and keep saving separate from approval. Add generic JSON-pointer-based source shortcuts for scalar and structured fields, aggregate every exact page citation, and state missing/unresolved links without inventing pages. A field-source jump keeps the complete field/editor view mounted while updating the original; ordinary next/previous navigation continues synchronized page review. Preserve API/model contracts, saved records and all warnings. Plan mode/TodoWrite are unavailable; this plan and the initial commentary are the planning check-in. Focused delegated work follows AGENTS.md; one owner runs builds.

### Review

- Replaced the two-step Prepare/Load handoff with explicit Review / edit actions at the result and All fields. A new local editor opens directly; repeated requests preserve unsaved agreement/invoice work until an explicit replace/keep choice. A consumed request cannot reopen itself after cancel or save.
- Named the Agreement master stage and Rent Agreement Master Repository, retained a visible local-unsaved badge, and placed Save draft version at the editor top and bottom with native validation. Saved versions expose separate approval/history, preserving authority and approval gates.
- Added shared model/schema-agnostic field source controls backed by exact JSON pointers and source IDs. Single-page shortcuts open the PDF directly; multi-page controls show all unique sorted pages, including descendant citations. Missing or ambiguous links remain explicit. Source jumps preserve All fields/Edit all fields and mounted unsaved inputs, reveal/focus the compact Original pane, and respect reduced motion. Supporting document editors use their own evidence and exact source identity.
- Test-first helper regressions failed before implementation, then passed. All 64 frontend tests, scoped JSX/React-hook/undefined-variable checks, final production Vite build and whitespace checks passed. Existing Browserslist and bundle-size advisories remain.
- Live UI checks passed at 1440px desktop and the normal 355px viewport without horizontal page overflow: scalar source page 7, a field with eight pages including page 24, preserved complete-field scope, native top-save validation, one-shot cancellation, replace/keep protection in both workflows, and no inherited invoice citations on an added tax document. Saved one separate synthetic draft, DEMO-RA-2026-90c2aace v1, to verify repository persistence; left it unapproved. No real agreement/invoice was saved, approved, reconciled or re-extracted. Screenshots retained in ignored data/runtime/paper-real-sample/; the user guide reflects the new flow. Browser console has no errors, and the temporary viewport override was reset.
- Read-only integrity follow-up: all currently listed original PDFs match their saved source hashes, and all 17 available preexisting baseline snapshots match. The older 19-resource fixture references one historical extraction (96656909-eacb-41b7-b66f-92d8d0f06f41) and its hash that are absent from the current API (404); the six-item history was already present at turn start. No deletion was performed in this task. The full older fixture therefore cannot pass; this preexisting history gap is separate from the verified UI changes.

# UniSensoryAI — Project Roadmap

## Document model provenance and related UI consistency — 2026-10-16

- [x] Trace saved model provenance through extraction, job APIs, shared history, and document views; reproduce missing labels in the live app.
- [x] Add failing regressions for model provenance, historical records, and related document/history presentation gaps.
- [x] Implement a shared, honest model display and persist available extraction provenance without guessing historical models.
- [x] Verify dashboard, document detail, upload history, and relevant PAPER screens; run focused backend/frontend checks and production build.
- [x] Record results, limitations, and lessons from the correction.

### Plan and scope

Repair the reported missing model labels and directly related inconsistencies while preserving existing uncommitted work and saved documents. Audit backend provenance and frontend presentation in parallel, then add focused regressions before changes. Prefer stored per-stage provenance over the current model selector or deployment defaults; records lacking historical identity must say so clearly. Plan mode and TodoWrite are unavailable in this session, so this written plan and commentary provide the planning check-in. No model reruns or business-data edits are needed for diagnosis.

### Review

- Root cause: PAPER extraction discarded the model identities returned by document and field capabilities, and completed-job metadata retained only extraction counts/status. Model identities now survive successful OCR/vision, field extraction, retries and review/repair results, queue persistence, and reopened history. Multiple identities are deduplicated in call order; native-only results may correctly contain none. API contracts are additive and require no database migration.
- Shared frontend presentation now renders saved identities consistently in the dashboard, document viewer/inspector, upload history and PAPER extraction details. The six existing uploads have no recorded historical identity and show Not recorded with an explanation. New results with explicitly empty provenance show No model recorded; pending PAPER jobs show Server configured. The current upload selector is never used to identify old runs.
- Fixed document metadata propagation (pages, file size, timestamps and model identity), full job refresh/polling updates, authenticated viewer refresh through the default proxy, exact document selection within multi-document jobs, and stale viewer/policy snapshots when changing documents. Chat with document now consumes a scoped, validated document handoff once; manually deselecting context stays deselected. Corrected the dashboard total tooltip and Chat browser title.
- Found and fixed a desktop layout gap during visual review: idle tips no longer consume the document workspace after history exists, and table columns retain readable document/model widths with contained horizontal scrolling on compact screens. Filename hover text exposes truncated names. Verified at 1280px and 900px with no horizontal page overflow; the temporary viewport override was reset.
- Verification: 61 frontend tests and 154 focused backend tests passed. New provenance and Chat regressions were observed failing before implementation. Production Vite build, scoped React-hook/undefined-variable checks, backend Ruff/Black/isort, scoped strict mypy and whitespace checks passed. Existing Browserslist/bundle-size advisories and three preexisting policy API mock warnings remain.
- Live checks passed for all six historical dashboard rows, exact next-document navigation and metadata, original PDF rendering, document inspector, upload-history details, PAPER extraction provenance, and document-to-Chat context with persistent manual deselection. Restarted only the local API after confirming zero active jobs; health, saved-job count and additive OpenAPI fields passed. No extraction was rerun, no chat was sent, and no saved business data was edited.
- Limits: historical model identities cannot be recovered from these records. Provenance describes retained successful results; a field stage that raises without returning a result cannot contribute its discarded intermediate call identities. Existing unrelated working-tree changes were preserved. No commit or push was requested.

## PAPER synchronized page review and compact layout — 2026-10-15

- [x] Add failing regressions for page-scoped text and canonical evidence selection, including missing pages and ambiguous/foreign citations.
- [x] Drive original and extracted page content from one page state, with an explicit complete-field editor that preserves unsaved changes.
- [x] Use compact responsive upload controls/history cards and multiple columns for short extracted values.
- [x] Verify page navigation, evidence links, draft preservation and responsive layout in the live UI; run frontend tests/build and record results.

### Plan and scope

The current page controls change only the original image; the extracted panel has no page scope. Add a deterministic projection of stored page content and exact evidence links, using no new model calls or backend changes. Default extraction review to the current page, retain a clearly labelled All fields view, and keep editable drafts mounted across view changes. Scope field references to the owning source document and do not guess missing page links. Use available width for short controls/history cards and canonical values while keeping long prose and narrow layouts readable. Plan mode/TodoWrite are unavailable; this written plan and initial commentary provide the planning check-in. Root owns page synchronization and integration; a focused agent owns compact upload/history layout.

### Review

- Added a deterministic stored-page projection with exact document-qualified evidence, nested JSON Pointer values and explicit missing-page/unlinked-evidence states. Four new regressions were observed failing before implementation and now pass, including ambiguous and foreign links, unchanged input snapshots, current draft values and safe null/zero/missing property handling.
- Both original and extracted page controls now update one selection. This page shows recovered text, tables, visual asset counts and only fields whose citations resolve to that page; All fields retains the complete extraction. Drafts open in Edit all fields and stay mounted while page review is selected. Page changes reset both pane scroll positions; desktop comparison panes have equal bounded heights. Warning counts and full evidence remain accessible.
- Moved extraction options into the responsive upload row and replaced full-width history rows with a responsive card grid. Short canonical values use available columns while long text/structured values span the grid. Unknown/null values do not force a full row. Compact scope buttons fit together without horizontal overflow.
- Live supplied-agreement checks passed: page 7→8 changes recovered text (1,743→1,543 characters) and linked fields (lease dates→renewal terms); extracted previous returns the original to 7. Both next buttons disable on page 38. A temporary unsaved identity survived source-page switching and returning to the full editor; the real draft was cancelled without saving. Desktop 1600px has four history columns, four upload-control columns and two short-field columns; 900px and restored normal 355px layouts fit without horizontal page overflow. Mobile Original/Extracted and keyboard page navigation stay synchronized, and extraction options stay within viewport bounds.
- Verification: 52 frontend tests pass; scoped JSX/React-hook lint and whitespace checks pass; production build passes with existing Browserslist/bundle advisories. A read-only peer review found and confirmed the null-span fix. Updated the testing guide. No backend, schema, model, persisted-source or approval behavior changed, and no extraction was rerun. Screenshots are retained under ignored data/runtime/paper-real-sample/paper-compact-history.png and paper-synchronized-page-review.png. Temporary viewport overrides are reset before handoff.

## PAPER guided UI and interaction polish — 2026-10-15

- [x] Inspect the current screens and define a simpler task-focused navigation without losing unsaved editors.
- [x] Separate document review, agreement approval and invoice reconciliation into clear workspace stages.
- [x] Apply progressive disclosure to field guidance, technical metadata, advanced inputs and synthetic testing tools; keep evidence, blockers and explicit approval requirements discoverable.
- [x] Add purposeful transitions, loading/status feedback and reduced-motion support using existing dependencies.
- [x] Verify stage switching, form preservation, evidence navigation and approval gates in desktop and compact layouts; run frontend tests/build and document results.

### Plan and scope

Polish the existing PAPER interface while preserving API/domain behavior and persisted records. Keep every workspace mounted across stage changes, move long implementation-facing explanations and developer tools behind labelled disclosures, and show the next useful action near the relevant result. Retain visible warning counts and decision blockers; do not auto-acknowledge exceptions or remove source inspection. Reuse the current design tokens and CSS transitions, with keyboard focus and reduced-motion support. Plan mode/TodoWrite are unavailable; this plan and the initial commentary provide the planning check-in. Focused agents own extraction/source presentation and agreement/invoice presentation; root owns the guided shell, shared motion/styles, integration and live verification.

### Review

- Added three keyboard-accessible stages: Documents, Agreements and Invoices. Extraction handoff and Use for invoice move to the relevant stage and focus its content. Workspaces stay mounted so switching stages preserves unsaved editors; reload still requires saving. Existing account/tenant/backend scope remounts remain in AppShell.
- Simplified upload/history cards, grouped agreement terms with a fallback for additional external schema fields, and added concise invoice payment summaries. Moved schema guidance, IDs, full OCR/downloads, JSON and synthetic tools into labelled disclosures. Warning counts, source discrepancies, payment conditions and explicit approval acknowledgements remain available. No models, API contracts, migrations or reconciliation rules changed.
- Added brief stage/disclosure transitions, interactive feedback and real loading indicators using CSS and existing icons. All PAPER motion has a reduced-motion override. Invalid controls reopen every containing disclosure and receive native focus; citation jumps reveal the compact original pane before scrolling.
- Verified the real-source result warning count, original page rendering and citation navigation, plus an extracted-to-editable agreement handoff. A temporary unsaved identity survived stage changes and keyboard navigation; that real draft was cancelled without saving. Desktop 1440px and normal compact 355px layouts have no horizontal page overflow, and the temporary viewport was reset.
- Passed a fresh synthetic full flow: DEMO-INSTALLMENT-2026-f52bb302 saved/approved, DEMO-INV-2b89f8ef reconciled to three review findings, approval disabled with reason alone, then enabled only after all three explicit acknowledgements and recorded successfully. Nested hidden-required-field validation was tested before saving. Read-only integrity verification confirms all 19 preexisting resource snapshots and original PDF hashes are unchanged.
- Verification: 48 frontend tests pass; scoped JSX/React hook checks and whitespace checks pass. Production build passes with existing Browserslist/bundle-size advisories. Updated documentation/PAPER_UI_TESTING.md for the new navigation. Screenshot proof is saved under ignored data/runtime/paper-real-sample/paper-guided-workspace-desktop.png. No commit/push was requested.

## Installment and withholding reconciliation with UI review — 2026-10-15

- [x] Inspect current pricing, tax, authority, duplicate claims and UI boundaries; agree backward-compatible typed contracts.
- [x] Write failing tests, then implement configurable deterministic installment and withholding checks with reviewed policy/rounding.
- [x] Prevent repeat billing of the same installment across different invoice numbers using atomic tenant-scoped claims.
- [x] Add editable agreement schedules, invoice installment/tax components, clear findings and a separate synthetic full-flow UI example.
- [x] Validate the supplied agreement/invoice mapping without inventing bank details, host identifiers, tax attachments or source periods.
- [x] Run backend/frontend regressions, live UI end-to-end checks and document the exact test flow and remaining source requirements.

### Plan and scope

Add optional typed terms and versioned pure reconciliation rules behind existing injection ports. Preserve signed legacy tax amounts, existing monthly/per-invoice comparison and approval/version/history behavior. Compare advance installments against explicitly approved schedule amounts and coverage rather than relabelling annual rent or inferring service periods from invoice dates. Keep VAT and withholding independent; use approved rate, precision, rounding and reference inputs rather than deriving tax law. Record conditional due-date/prerequisite review, retain source discrepancies, and fail safely on unknown or conflicting inputs. Add a distinct synthetic scenario for full UI testing; the real source remains unapproved until the user resolves identity, bank, documentary and policy inputs. Keep private sample artifacts ignored and untouched automated extraction history. Plan mode/TodoWrite are unavailable; this checked plan and commentary provide the planning/check-in record. Focused agents own rules, frontend and read-only adversarial review; root owns integration, atomic repeat-billing protection and live verification.

### Review

- Added optional typed installment schedules and independent approved withholding policies, explicit VAT/withholding/rounding components and separately recorded reviewed allocation. The injected versioned rules are pure and model agnostic; configuration enables them in this deployment while packaged/library defaults remain disabled. Existing legacy signed-tax and monthly/per-invoice behavior passes regressions. JSON snapshots require no new migration.
- Added exact decimal checks for gross, approved rate/rounding, VAT evidence, withholding certificate identity/amount and net payable. Missing or conflicting monetary evidence blocks approval. Reviewed allocation, conditional prerequisites and the retained source discrepancy require explicit AP acknowledgement. Stable installment IDs survive amendments; only the selected obligation must fit the selected version's effective interval.
- Reused atomic tenant-scoped duplicate claims for eligible installments across different invoice numbers and agreement versions. Both claims roll back together, losing invoice claims do not reserve another installment, and approval rechecks retained ownership. Claims remain reserved after rejection; release/cancellation is not implemented.
- Added agreement schedule/policy editors, invoice component arithmetic, installment selection and separately explained allocation, actual-certificate input fields and a clearly synthetic demonstration. Saved IDs are locked in both normal and JSON revision paths. Existing original/evidence review remains available. Fixed intrinsic grid overflow found during actual compact-screen testing.
- Saved separately labelled UNAPPROVED real-source mapping under ignored `data/runtime/paper-real-sample/`: schedule gross 983,333,333 + 655,555,555 = 1,638,888,888; invoice gross 983,333,333 less withholding 98,333,333 = net 885,000,000. Preserved annual source price, IDR 3 discrepancy, both contingent installment conditions and unknown source service dates. Whole-lease allocation, downward whole-Rupiah rounding and explicit zero VAT are proposed review inputs. External IDs, bank and actual certificate remain unresolved; no real master/case was saved or approved.
- Verification: **634 selected backend tests passed**, including new rules, API/SQLite lifecycle, extraction, queues, chat and policy; four existing warnings remain. **48 frontend tests passed**, and production build passed. Scoped strict mypy, Ruff, Black/isort and whitespace checks passed. A 44-test lifecycle/storage rerun passed after final typed-access cleanup. Existing bundle-size and Browserslist build advisories remain.
- Live local PostgreSQL/UI flow passed: saved/approved a new synthetic agreement, reconciled stage one to three review findings, explicitly acknowledged each, recorded AP approval, then submitted a different invoice number for that same installment and observed Duplicate with approval disabled. All 19 preexisting resource snapshots and original PDF hashes remain unchanged. Both saved/editor workflows fit the normal 355px viewport (347px page width); desktop 1440px also passed, and temporary viewport override was reset. API, web, PostgreSQL and Redis are healthy. The approved synthetic case remains open; screenshot saved as `paper-installment-approval-desktop.png` in ignored private runtime artifacts.
- The rules support one complete installment per invoice. Partial splits, conditional deposit accounting, working-day deadline calculation, payment execution, SAP posting and email remain separate capabilities. The guide in `documentation/PAPER_UI_TESTING.md` documents exact UI steps, synthetic JSON examples and the required real-source review inputs. No commit/push was requested.

## Agreement evidence repair, source verification and review flow — 2026-10-15

- [x] Diagnose the 15 missing-evidence warnings from persisted output and actual serialized field requests.
- [x] Add failing regressions and repair provider-neutral extraction/evidence behavior without accepting unsupported quotes.
- [x] Rerun the real agreement as a new persisted attempt and compare canonical fields against original page images.
- [x] Add original PDF alongside extracted fields/draft editing with page-aware evidence navigation and responsive access.
- [x] Explain extraction → corrected draft → approved master → invoice reconciliation → AP decision in the UI and guide.
- [x] Verify backend/frontend regressions, original-source integrity, live UI behavior and remaining uncertainties.

### Plan and scope

Preserve the earlier attempt and all warnings. Diagnose model response versus evidence verification, then repair generic orchestration/prompting rather than hardcoding this agreement. Source verification must distinguish automated evidence matching from original-PDF fact checks. Keep private source/model artifacts in ignored `data/`; do not approve accounting records during extraction tests. Add an accessible source-review component shared by extraction and editable draft contexts, with desktop side-by-side and narrow-screen alternatives. Plan mode and TodoWrite are unavailable, so this checked plan and commentary are the planning/check-in record. Use focused agents under AGENTS.md; root owns live reruns, integration, original-page review and final verification.

Investigation changed the implementation plan: schema-valid output with an empty evidence array bypassed completion, while visual checks found separate semantic mistakes. Stronger descriptions alone failed on the real source. An opt-in focused pass now selects operative blocks using the external schema and re-extracts small field batches; the private rerun corrected premises and full payment/renewal conditions. Literal quotation copying remains unreliable, so evidence completion will select deterministic source spans that the host resolves back to exact original substrings. No fuzzy acceptance or automatic semantic/accounting approval is introduced. Deployment opts into focused review; reusable defaults and existing canonical field names remain compatible.

Live verification exposed a separate intermittent Docker DNS failure before OCR: provider connection probes alternate between `ConnectError` and HTTP 200 while Windows resolves the same host. Preserve the failed attempt and add only bounded connection-establishment retries inside the provider's existing total inference deadline; do not retry HTTP/model responses, hardcode endpoint addresses, or change network security. Resume the full saved rerun after this narrow fix is tested.

### Verification checkpoint

Original-page review of the saved full OCR rerun caught a regression: automatically replacing narrative fields with selected citation fragments lost an installment amount, started mid-word, duplicated terms and omitted qualifications. Stop that approach. Evidence completion must preserve candidate values; exact spans remain separate citations, and narrative leaves explicitly require source review. Re-run field understanding against the unchanged, hash-verified 38-page OCR as a new persisted attempt using the existing injected document capability and worker, recording OCR reuse provenance. Compare conditions against the original pages again before accepting the result.

The next saved field run repaired payment and renewal terms, with 23 literal citations and no missing-evidence gaps, but original-page verification rejected a null currency and a termination summary missing a cumulative condition. A focused response could omit requested keys and bypass retries because only the relaxed full schema was checked. Add test-first projected-schema validation requiring requested keys, and improve the external other-terms description to retain grounds, remedies and exceptions. Preserve this rejected attempt; do not fill values manually or describe literal citation coverage as semantic correctness.

The bounded deployment review now handles one field per batch (32 maximum batches) and allows 16 source blocks. Original-page review shows other terms span at least ten page blocks across fit-out, deposit, restoration and termination, exceeding the previous eight-block cap even before paired renewal review. This is a host configuration change limited to the existing agreement schema allowlist; reusable defaults and other workflows remain unchanged.

- Added test-first evidence completion using exact host-resolved span IDs, focused schema-guided review with requested-key validation/retries, and opt-in narrative source-review warnings. Evidence completion cannot rewrite canonical values. Deployment focuses review only on the rent agreement schema; existing public evidence/canonical contracts remain compatible. Connection retries are validated, deployment-owned and limited to establishing a connection within the existing inference deadline.
- Added a model-free original-page renderer behind an injected ABC, tenant authorization before file access, bounded PNG output, and non-cacheable private responses. Source review is shared by extraction results and agreement/invoice editors, with exact evidence-to-page navigation, zoom, narrow-screen view controls and image retry preserving edits.
- Final selected backend regression set: **492 passed**, with four pre-existing test warnings. Frontend: **40 passed**, and the production build passed. Scoped strict typing, Ruff, Black/isort and whitespace checks pass. Live desktop/narrow layout and editor preservation passed. Saved the final private side-by-side screenshot and reset the temporary viewport override; the normal 347px content viewport has no horizontal page overflow.

### Original-source acceptance findings

- Fresh queued OCR completed all 38 pages with 59,569 characters and no document warnings. Field-only follow-up jobs explicitly reused that unchanged, hash-verified document through the existing injected capability and normal worker/result persistence. Earlier artifacts remain immutable.
- Final automatic attempt `676e7411-383a-4be4-918c-553491503193` has 29 literal citations and zero `missing_evidence` warnings, but **fails semantic acceptance**: the model selected the tenant as landlord, left rent type unresolved, and omitted deposit prerequisites. Its 46 raw diagnostics remain visible (42 after exact duplicate removal in the UI). Literal evidence coverage does not resolve those errors.
- Stop treating additional model reruns as proof of correctness. Keep this attempt partial and prepare a separately labelled, agent-assisted source-review candidate with corrected source facts, unknown host identifiers and bank details, and independent review provenance. Do not overwrite automatic history, approve an agreement, reconcile the real invoice or create payment/posting side effects.
- All seven history attempts retain source hashes; six completed and one failed attempt are preserved. Existing one synthetic agreement and four cases remain unchanged. API, web, PostgreSQL and Redis are healthy.

### Final review

- Saved a separate `agent_assisted_manual_source_correction` candidate and unapproved `AgreementDraft` under ignored `data/runtime/paper-real-sample/agreement-source-reviewed-*.json`. Source SHA256 and untouched automatic-result hashes match. Both schemas pass; all 39 reviewed quotes are raw-exact source-block substrings with populated canonical paths. Fourteen primary source/unknown-preservation checks pass. Thirteen reviewed other terms retain selected operative conditions and exceptions; this is not a complete legal abstract of all 38 pages.
- Corrected landlord role, fixed pricing type, payment/deposit prerequisites and selected contractual conditions. Preserved annual pricing, conditional renewal and the IDR 3 source arithmetic discrepancy. Bank details and external vendor/store identifiers remain unknown. Kept all 46 historical automated diagnostics clearly labelled as pre-correction findings, plus eight explicit source-review limitations.
- Loaded corrected values into the unsaved editable agreement form and verified payment, renewal, all other terms, extensions, landlord and unknown identities/bank. The UI retains original automated evidence; replacement reviewed evidence is in the separate draft artifact, explicitly recorded in the version reason. No agreement was saved or approved. Narrow Original/Fields switching preserves corrected terms; the review tab remains open.
- Extraction pipeline regressions and UI checks pass, but unassisted model semantic acceptance remains failed and visible. Real invoice reconciliation still needs external identities, documentary support and a versioned installment/withholding rule. No real approval, posting, email or payment was performed; no commit/push was requested.

## PAPER PDF extraction and persistent upload history — 2026-10-15

- [x] Trace current workers, durable jobs/results, extraction configuration and draft editor boundaries.
- [x] Write failing tests for queued PAPER extraction, tenant-scoped history/results and evidence-preserving draft mapping.
- [x] Add an additive worker-dispatched extraction workflow with persisted original files, document output, field results, warnings and safe failures.
- [x] Configure deployment-owned OCR/field profiles and clarify the model-neutral response protocol with regression coverage.
- [x] Add PDF upload, progress/history, source/results access and deliberate import into editable agreement/invoice drafts.
- [x] Run focused backend/frontend checks, start updated services and verify actual UI extraction/history/reload behavior.
- [x] Document verified behavior, remaining limitations and test instructions.

### Plan and scope

Reuse existing ingestion jobs and worker backends through an additive workflow dispatch hook. Keep extraction services independent of PAPER approval/reconciliation. Persist extraction artifacts before draft import; preserve literal source evidence and original warnings through user edits. Unknown identities/dates stay editable and unapproved. History must be tenant scoped, survive browser reload and show failed/pending uploads as well as completed output. Existing document processing, manual PAPER forms and JSON import remain compatible. Deployment selects OCR and field providers; no provider credentials or model-specific behavior enters the UI/PAPER domain. Use focused subagents as required by AGENTS.md, TDD for new pipeline behavior, and integration/UI verification. Plan mode and TodoWrite are unavailable, so this checked plan and commentary are the planning record.

### Review

- Added queued `/v1/paper/extractions` upload/list/detail/original/retry endpoints using the existing tenant-scoped ingestion/document tables, with no migration. Original PDFs and immutable detailed JSON artifacts live in configured private upload storage; list responses carry light metadata. Partial field failures preserve recovered document text and warnings. Retry creates a new source copy/history attempt. Both queue backends dispatch the optional workflow while retaining the existing processing callback for other jobs.
- Added deployment-owned OCR/field profiles, environment substitution, explicit evidence-array response instructions, and generic external schema field descriptions. PAPER/UI choose no model. Docker now selects Redis and a validated 1800-second full-document deadline; each inference call retains its 60-second budget. Library defaults remain unchanged. The original 300-second deadline failed on the long sample; after upgrading the old worker, the single interrupted sample was explicitly handed back to the queue using the tested recovery helper.
- Added PDF upload, text/multimodal choice, polling, paginated extraction history, original/text/JSON access, evidence/warning review, and an explicit Prepare → Load/Replace handoff to editable agreement/invoice drafts. Missing host IDs/dates remain unknown. Sidebar Upload history and Documents now load server records across browser sessions, use original filenames, and clear scope on account/tenant/backend changes. Accepted uploads refresh shared history. Unsaved form edits remain local; explicit agreement/case save persists edits.
- TDD reproduced the new worker/draft boundaries and review findings before fixes. Fixed precommit/cancelled file cleanup, independent retry sources, after-commit deletion cleanup, Redis postcommit housekeeping, graceful interruption handoff, selected-backend binding, global history refresh, original filenames, and generic history credential serialization. Generic retries now use the queue-neutral requeue operation. Redis startup no longer marks durable pending/active work failed.
- Verification: **420 focused backend tests passed**, including existing extraction/PAPER/API/worker/storage behavior and real SQLite queued-history reopening; **36 frontend tests passed** and the production build passed. Scoped strict mypy passed **11 new source files** using the cached Python 3.11 tool; changed boundaries passed Ruff/Black/isort and whitespace checks. Existing mock coroutine warnings and Vite bundle/Browserslist advisories remain. No full-suite/GPU/production availability claim.
- Live Docker checks: the supplied invoice completed in multimodal mode with one page, 1,120 text characters, two visual assets and 10 evidence quotes. The 38-page agreement completed OCR with 58,680 characters; canonical output is **partial**, with 15 missing-evidence warnings and no verified field quotes. Browser verification loaded both into editable drafts with retained diagnostics, tested unsaved replacement controls, submitted an additional invoice via the PDF picker, and confirmed its completion plus shared Documents/history. Saved invoice output survived the API recreation; history survived browser navigation/reload. Browser file-picker automation stalled for an extended period despite its requested timeout, but ultimately completed; no further picker retries were needed.
- Sources/results remain under ignored private `data/`; no accounting approval, payment, email or SAP operation was created. Verified all three saved original PDFs and result document IDs against source SHA256 values; the existing one synthetic approved master and four cases remain available. All four Docker services are healthy. Redis workers are coroutines inside the API process (default four), not separate worker containers. Graceful shutdown requeues PAPER work; abrupt consumed-job loss still needs recovery because existing Redis lists have no acknowledgement leases. Ambiguous completion commits conservatively retain artifacts, with legacy failure/retry behavior at that boundary unchanged. Extraction correctness still needs human source review, particularly scanned bank details, advance installments and withholding rules.
- Updated README and PAPER/extraction test/configuration guides. Existing unrelated changes were preserved. No commit/push or production deployment was requested.
- Final browser layout review found the existing fixed sidebar consumed almost the whole 347px in-app viewport. Added a compact accessible icon rail, reduced small-screen padding, a usable account menu, and wrapping workflow tabs. Reverified the 36 frontend tests/build. Browser measurements show no horizontal page overflow at 347px (64px rail) or desktop 1272px (256px sidebar); temporary viewport override was reset. Saved private narrow/desktop proof screenshots in `data/runtime/paper-real-sample/` and left the agreement result deep link open for review.

## Real agreement and invoice extraction check — 2026-10-15

- [x] Inspect the supplied PDFs and identify native-text/OCR requirements.
- [x] Verify the running extraction configuration and exercise its real behavior.
- [x] Read the scans with local OCR and visual checks; map source facts to canonical schemas with page evidence and explicit unknowns.
- [x] Validate the candidate agreement/invoice data and compare identity, periods, amounts, and classification inputs.
- [x] Provide local review artifacts and record proven behavior, gaps, and next steps.

### Plan and scope

Test the two user-supplied files without changing workflow code or publishing an accounting decision. Keep private source content and review artifacts in ignored local storage. Distinguish application extraction from any local OCR/manual verification used to assess the documents. Preserve source references and unknown business IDs. Plan mode and TodoWrite are unavailable; this checked plan and commentary are the planning record.

### Review

- Both supplied files are scans: 38 agreement pages and one invoice page, with no native PDF text. Live API native-only calls return partial/empty text, while multimodal mode retains invoice images. OCR requests currently return `503 unknown_model_profile`: the running deployment has no extraction profiles configured.
- An isolated instance of the existing provider-neutral extraction service, using the configured cloud vision adapter and existing credentials, successfully OCR processed all 39 pages. Agreement output contains 58,645 text characters; invoice output contains 1,120. No provider/model logic was added to PAPER, and no live extraction configuration was changed.
- Default model field responses failed strict evidence validation because they returned an object instead of the evidence array. Clarifying the response protocol in the private test enabled structural extraction. Generic external schema descriptions then corrected invoice field selection; its 11 returned evidence quotes verify. The agreement model still returned 44 evidence warnings and made semantic mistakes involving the property address, payment timing and annual pricing. Its untouched results and warnings are retained separately from the manually corrected review candidate.
- Private source-checked agreement terms, an unapproved `AgreementDraft`, invoice terms, provenance, and validation results are saved under ignored `data/runtime/paper-real-sample/`. All three Pydantic contracts validate. Verified 38 agreement quote/source/pointer references and 11 invoice references, both source SHA256 IDs, installment totals, invoice gross-to-installment equality and net-payable arithmetic. Preserved unknown host IDs and service dates, the annual-versus-total source discrepancy, and withholding rounding. High-resolution account review indicates a match but still requires human confirmation of degraded scan detail before payment.
- No agreement/case record, classification, approval, payment, email or SAP side effect was created. Vendor/store authority, accounting commencement, renewal assessment, service-period linkage and documentary requirements remain review inputs. These advance installments and PPh withholding require explicit host-owned rules; recording them in schema extensions does not make the existing pricing engine implement them. The current PAPER screen supports structured review/import, with PDF upload-to-draft prefill still pending.
- Recommended next work: configure the deployed extraction profile; add a regression-tested evidence-array response contract; connect PDF upload/extraction to editable draft prefill; add typed installment/prepayment and withholding-versus-VAT reconciliation rules. No production source changes or full regression claims in this sample assessment. Existing unrelated changes were preserved.

## One-command Docker development stack — 2026-10-15

- [x] Inventory and back up the existing PostgreSQL volume; record data/settings baselines.
- [x] Add API and Vite web services with container-aware connections, automatic migrations, and existing uploads/configuration mounts.
- [x] Remove the unnecessary Redis host port binding without touching the other project's Redis.
- [x] Preserve production overlay behavior and document local/manual startup and data handling.
- [x] Verify configuration, image builds, live API/web/proxy behavior, and retained database rows/files/settings.

### Review

Completed and running with all four containers healthy. The verified manual API/Vite processes were replaced by containers on the same localhost ports; the other project's Redis remains running on host port 6379. This stack's Redis has no host port binding.

- Preserved `unisensoryai_postgres_data` and `unisensoryai_redis_data`, mounted existing `data/`, `configs/`, source/migrations, and frontend env files. Migrations run before the single-process API starts; the configured queue backend is retained. OAuth callbacks retain a public browser URL.
- Saved the pre-change database dump and comparison baselines in ignored `data/backups/`. All 14 table content hashes match exactly after startup, including the agreement, four invoice cases, history/decisions and accountant role. All seven upload checksums and both actual env files match the originals.
- Manual/Docker JSON responses match exactly for health, OpenAPI, auth identity, review context, agreement listing and invoice-case listing. Web `/`, `/paper`, `/health` and PAPER proxy routes return 200. Browser reload shows the retained approved agreement and AP-enabled reviewer.
- Both images built successfully; live API-to-Redis ping, upload-directory write access (temporary probe removed), and credential-free HTTPS reachability to the configured cloud host passed.
- Focused backend regression suite: **60 passed** (`test_upload_storage`, `test_api`, `test_ingestion_queue`, `test_redis_queue`). Frontend: **24 passed**, production build passed. New helper/tests pass Ruff and Black; helper passes strict mypy. Existing legacy lint findings were left unchanged. Whitespace check passed.
- Parsed development, production and optional GPU overlays: production excludes Vite, resets development host ports/bind mounts and selects the runtime image; GPU configuration enables local-model dependencies/device/cache. The default cloud stack was exercised; GPU inference and production deployment were not run.

Existing unrelated source changes remain in place. Use `docker compose up --build` for foreground startup, `docker compose stop` to stop, and never add `-v` to `down` when retaining database volumes.

## PAPER web review interface — 2026-10-14

- [x] Add tested, tenant-scoped agreement listing and current review capabilities APIs.
- [x] Add a modular PAPER client, schema-driven field forms, JSON import/export, and synthetic sample builders.
- [x] Build agreement creation, version review, approval, and effective-date lookup screens.
- [x] Build invoice package creation, findings, corrections, version history, and AP decision screens.
- [x] Integrate PAPER navigation, run backend/frontend checks, and exercise the flow in the browser.
- [x] Start the frontend, document the test steps and actual verification, and preserve existing workflows.

### Plan and scope

The user selected **web interface for existing workflows first**. Build additive React screens over the implemented PAPER services; email and SAP remain later work. Keep ordinary fields editable through schema-driven forms and expose advanced JSON for external extensions and retained evidence. New draft and invoice samples use unique synthetic business identifiers and save only on explicit user submission. Reviewer permissions, requirements, and allowed AP exceptions come from the backend; existing role, tenant, stale-version, and policy guards remain authoritative. Keep model construction out of the UI and PAPER domain. The current extraction screen remains available; this phase supplies typed field entry/import rather than inventing document inference. Verify the actual browser flow and a production frontend build. Plan mode and TodoWrite are unavailable in this session, so this checked plan and the commentary check-in serve as the planning record.

### Review

- Added tenant-scoped `GET /v1/paper/agreements` listing latest snapshots with deterministic pagination, and a separately composed `GET /v1/paper/review-context` router returning persisted-role permissions and host-owned requirements/exceptions. No migration or approval authority change. The listing port is optional for existing external repository adapters, preserving their lifecycle compatibility.
- Added `/paper` and sidebar navigation with separate agreement/invoice workspaces, a shared API client, server-schema forms, guarded JSON import, and isolated unique synthetic sample builders. Supports drafts/publication, date lookup, append-only corrections, AP decisions, findings, provenance, duplicate dispositions, and paginated version history. Decimal amounts and account IDs remain strings. New schemas and fields use the same catalog; the UI constructs no model or provider.
- TDD demonstrated failures for the 11 new backend checks, frontend helper/API imports, AP decision eligibility, package replacement/identity handoff, and exact source-ID parsing before implementing their behaviors. Corrected review findings around discarded editors on access refresh, stale document collections during import, source-ID comma splitting/synchronization, and unapplied JSON edits. Backend authority, tenant scope, reference checks, and structural blockers remain intact.
- Verification: **223 PAPER/API tests passed** (193 PAPER plus 30 API), **24 frontend tests passed**, scoped React hook/unused checks passed, and the production Vite build passed. Backend changed sources passed Ruff, Black, isort, and strict mypy. Existing AsyncMock warnings and Vite bundle-size/Browserslist notices remain; no full-suite or live extraction-accuracy claim. `git diff --check` passed.
- Browser verification against PostgreSQL exercised draft creation/approval, preserved extensions, unapplied JSON save blocking, complete invoice matching/AP approval, missing-tax correction into version 2, historical decision controls, explicit bank exception acceptance, duplicate import/blocking, retained unsaved edits on access refresh, and reload persistence. Publishing agreement version 2 caused a stale AP approval to fail; reassessing generated case version 3, then AP approval succeeded against the new reference. Existing Dashboard and Chat screens loaded through navigation; no inference or communication was submitted.
- The backend is running on `127.0.0.1:8010` (server PID **48780**, uv launcher **45600**), frontend on `127.0.0.1:5173` (PID **26520**), and the existing PostgreSQL service remains healthy. Metadata/logs are in ignored `data/runtime/paper-backend.*` and `paper-frontend.*`. The PAPER browser tab remains open. Browser testing retained one uniquely named synthetic agreement (two approved versions) and four cases, including a duplicate; these are labelled synthetic examples.
- Updated the web/Swagger testing guide, README, and current assessment follow-up. Saved proof screenshot `documentation/screenshots/paper-review.jpg`. PDF upload/automatic extraction-to-package mapping, email/SAP, automatic accounting classification, and event/rematch automation remain future integrations under the user's selected scope. No commit, push, deployment, mailbox/SAP side effect, or new role grant was performed.

## Run PAPER migrations and backend for Swagger testing — 2026-10-14

- [x] Verify the configured database target, installed runtime, migration state, and port 8010.
- [x] Apply the authorized migrations to the configured database and verify the revision/tables.
- [x] Repair the stale virtual environment's missing declared dependency before restarting the backend.
- [x] Reproduce and fix the existing HTML preview route's invalid response class that blocks Swagger schema generation.
- [x] Start or reuse the backend and verify health, Swagger, and PAPER routes.
- [x] Record the running process, testing URL, and any approval-role prerequisite.
- [x] Create the explicitly authorized local test reviewer and verify approval/reconciliation against PostgreSQL without retaining synthetic business records.

### Plan and scope

The user explicitly authorized applying migrations and starting the backend for local Swagger testing. Use the same configured database for migration and server startup, keep credentials out of output, preserve existing data/workflows, and run the backend as a hidden background process. Check approval readiness without creating agreements, invoices, or granting user roles unless further authorization establishes the intended reviewer.

Startup finding: local PostgreSQL is not listening, the project has no running database container, and `postgres:17-alpine` is absent. Start the configured Docker Compose `db` service; obtain its configured image if needed. Compose created the project's network and volume while reporting the missing image. After database readiness, inspect migration state and upgrade normally; do not assume prior tables exist.

Re-plan after startup verification: PostgreSQL is healthy and all five migrations applied successfully to the new local database; revision `dc728f04a912` and seven PAPER tables are verified. The API exited during import because `.venv` lacks the declared `jsonschema` dependency. Inspect all runtime requirements and install the missing locked dependency closure without broadly replacing the existing model environment. The development tenant exists, but no `dev-user` record exists; approval-role setup requires an explicit reviewer choice.

Second startup finding: the repaired environment imports the backend, but the existing HTML preview endpoint declares `response_class=None`, causing full OpenAPI generation to fail. Add a failing full-application Swagger regression, replace that declaration with `HTMLResponse`, and verify the existing preview response plus PAPER route schemas before relaunching.

### Review

- Started Docker Compose's configured PostgreSQL 17 service. Its image was absent and was downloaded; the new project volume initialized a local database at `127.0.0.1:5434/unisensory`. All five migrations applied successfully through `dc728f04a912`, and all seven PAPER tables were verified. No existing data volume was deleted or replaced.
- Installed the missing `jsonschema` package and its locked dependency versions into `.venv` using uv's offline cache. Other model/runtime packages were retained. Added a failing full-application OpenAPI test, then replaced the legacy HTML preview route's `None` response class with `HTMLResponse`; the handler's existing HTML behavior is preserved.
- The backend runs as a hidden background process bound to `127.0.0.1:8010`; server PID **28272**, uv launcher PID **37736**. Process metadata and logs are in `data/runtime/paper-backend.json` and `paper-backend.stdout.log` / `paper-backend.stderr.log`. Health, Swagger HTML, OpenAPI, the PAPER schema catalog, and invoice-case listing all returned **200**; both approval endpoints are registered.
- The user selected Swagger examples and explicitly approved creating a local development reviewer. Persisted `dev-user` in tenant `default` with role `accountant`; authentication remains disabled under the existing local configuration. The actual agreement and AP actor guards recognize that persisted role. No OAuth login is needed for this local Swagger session.
- A rollback-only test using the actual PostgreSQL adapters and services passed agreement draft/publication, invoice matching, and AP approval. Temporary synthetic business records and duplicate claims were rolled back, and absence of their agreement/case headers was verified. Only the authorized development reviewer was retained.
- Verification after the fix: **30 API tests passed** (including the new Swagger regression) and **182 PAPER tests passed**. Existing AsyncMock warnings remain in API tests. `git diff --check` passed. Updated the UI guide and assessment with the actual local startup and PostgreSQL verification.
- No model inference, browser interaction, mailbox/SAP side effects, concurrent PostgreSQL stress test, commit, or push was performed. The backend and database remain running for the user's Swagger testing.

## PAPER manual reconciliation and UI testing — 2026-10-14

- [x] Define validated package, reconciliation, case version, and AP decision contracts; demonstrate failing tests before implementation.
- [x] Implement model-independent, configurable completeness and deterministic matching against approved agreement versions covering the invoice period.
- [x] Add durable tenant-scoped case versions, atomic duplicate claims, and audited AP decisions with stale-version/reference guards.
- [x] Expose additive authenticated case APIs and configuration without changing existing workflows.
- [x] Provide ready-to-paste Swagger UI scenarios for agreement creation/approval, matched and incomplete cases, mismatches, duplicates, overrides, and stale approval.
- [x] Verify focused tests, migration structure, existing regressions, lint/types/formatting, and document actual results.

### Plan and scope

Proceed with the next manually supplied package phase: typed extraction results and source references enter a durable case; deterministic rules identify completeness, identity, dates, bank, amount, and tax inconsistencies against approved agreement versions. Decimal arithmetic does not infer tax law or arbitrary payment schedules. Fixed-rent comparison requires an explicit supported billing basis; unsupported pricing requires review. AP decisions apply to an exact case and reference/policy version, with explicit, configured exception overrides; incomplete packages, duplicates, missing authoritative agreements, and stale decisions cannot be approved. New case versions invalidate the prior version's AP decision. Libraries use injected ports/services and contain no model construction. Additive SQL storage and APIs preserve prior workflows. Source artifacts remain host-owned; email/SAP/payment and background event orchestration remain later work. Proceeded with the recommended Swagger testing assumption after no answer to the optional web-screen preference question.

### Review

- Implemented validated source packages, deterministic rules, versioned assessments, case repository/rule interfaces, and `InvoiceCaseService` under `src/paper/reconciliation`. Settings and versioned injected rules enter the policy fingerprint; imported business modules construct no model or server/database dependencies. Decimal comparisons retain exact source precision and require explicit supported pricing semantics.
- Added tenant-scoped case, immutable version, immutable AP decision, and durable duplicate-claim tables through `dc728f04a912`. Storage uses tenant-qualified joins/composite foreign keys, latest-version guards, caller-owned transactions, case/reference locks, and atomic duplicate claims. Exact vendor/invoice claims survive correction and rejection. Only the original case can reuse its own claim.
- Added six authenticated case APIs with bounded validated inputs, persisted reviewer roles, shared PAPER rate limiting, storage deadlines, commit-before-success behavior, and safe error messages. AP approval verifies current reference/policy/content and requires explicit acceptance of every permitted unresolved code. Missing information, identity/period/currency blockers, duplicates, and stale case/reference/policy versions cannot be overridden. Rejection and historical decisions remain auditable.
- TDD covered contracts, rules, lifecycle, storage, and API integration. Review regressions first reproduced incompatible custom-rule fingerprints and an insufficient finding limit, then passed after the fixes. Rules are bounded to 64 extensions and 100 findings each; valid 100-document packages retain all built-in findings.
- Verification: **182 PAPER tests passed**, including actual synthetic HTTP flows through authorization, approved master, reconciliation, and SQLite storage. All three example JSON files were exercised through those endpoints. **204 existing extraction/API/auth/services/chat/policy tests passed**, with four pre-existing AsyncMock warnings. Strict mypy passed for 62 implementation files; Ruff, Black, and isort passed for 78 implementation/migration/test files. Python 3.10 syntax passed for all 62 implementation files.
- Alembic has one head, `dc728f04a912`; offline PostgreSQL upgrade/downgrade adds/removes only the four case tables. An offline wheel build matched current sources and three packaged YAML defaults; isolated imports/configuration and all five schemas loaded without API, database, or ML startup. Guide decision bodies and local example links validated. Swagger generated bearer authorization and typed package, revision, and decision forms. `git diff --check` passed.
- Saved `documentation/PAPER_UI_TESTING.md` and `examples/paper` with complete Swagger examples, authentication/role prerequisites, expected outcomes, correction/override/duplicate/stale-reference scenarios, and mapping from real PDF extraction. Updated the architecture and assessment guides to distinguish implemented manual reconciliation from future background/email/SAP orchestration. The existing main web app still has no PAPER page.
- Limits: no live database migration, concurrent PostgreSQL stress test, browser interaction, live model accuracy, accounting-rule validation, or full-suite run was performed. Mailbox/reply correlation, vendor communications, automatic rematch, SAP/payment, and dedicated web screens remain separate work. No commit, push, or deployment was performed.

## PAPER schemas and approved agreement master — 2026-10-14

- [x] Define external PAPER schemas and the agreement identity, version, approval, and repository contracts.
- [x] Write and demonstrate failing schema, master lifecycle, persistence, and API tests before implementation.
- [x] Implement model-independent schemas and a tenant-scoped, append-only agreement master with approved effective-date lookup.
- [x] Add SQLAlchemy persistence and an additive Alembic migration; expose authenticated, role-checked PAPER APIs without changing existing workflows.
- [x] Verify new contracts, approval/version concurrency guards, tenant isolation, migration structure, and existing workflow regressions.
- [x] Document extraction-to-master embedding, approval semantics, deployment migration, and actual verification results.

### Plan and scope

Phase one supplies five external extraction schemas (agreement, rent invoice, tax invoice, utility statement, supporting document) and a reusable agreement master. Draft versions retain source IDs and field evidence; immutable content and a separate approval record preserve audit history. Only approved versions effective on the requested date are returned for matching. Approval explicitly records a reviewer classification and rule reference; this phase does not invent accounting rules or implement invoice matching, email/SAP connectors, or the dashboard. APIs use the existing authenticated tenant identity, resolve approval roles from persisted users, and commit only successful mutations. Repository interfaces remain independent of FastAPI, SQLAlchemy, and inference providers. New unit tests mock database sessions; isolated database integration tests exercise actual constraints separately.

### Review

- Implemented five version-1 external schemas in `src/paper/schemas`, tenant-scoped lifecycle contracts and service in `src/paper`, an injected SQLAlchemy adapter, three additive database tables, and eight authenticated `/v1/paper` routes. Existing extraction, document pipelines, chat, and policy implementations are unchanged; the server only adds the router.
- Approval retains reviewer classification/rule references and audit identity/time. Missing required or rent-specific terms block publication; retained extraction warnings require explicit acknowledgement. New drafts retain previous approved authority. Effective-date lookup selects the latest started approval, then checks expiry, so an ended amendment cannot resurrect older terms.
- Persistence uses shared header updates for revision/approval locking, expected-version guards, tenant-qualified joins/composite foreign keys, unique identity/approval constraints, and separate immutable snapshots/approval records. Caller transactions own commits. Trusted hosts own original artifact retention and role assignment.
- TDD: missing-contract tests failed before implementation; review-driven tests reproduced missing payment requirements, unacknowledged extraction warnings, empty required extensions, and expired amendment fallback before their fixes. Unit tests mock sessions; integration tests use an isolated SQLite database with explicit transaction control.
- Verification: **90 new PAPER tests passed**. A separate existing extraction/API/auth/service/chat/policy regression subset passed **204 tests**, with four existing AsyncMock warnings. Strict mypy passed for 33 implementation files; Ruff, Black, and isort passed for 41 new implementation/migration/test files. Python 3.10 syntax passed for 33 implementation files; the guide's Python/JSON examples and six source links validated.
- Alembic has one head, `8b3e1c725f60`; offline PostgreSQL upgrade/downgrade generated only the three PAPER tables. An offline wheel build and isolated extracted-wheel smoke test verified current sources, packaged policy YAML, all five schemas, and library imports without API/database/ML startup. `git diff --check` passed.
- Focused read-only reviews verified schema/service/storage separation and final approval/supersession logic. A configurable empty-dictionary completeness edge was found and fixed with a failing regression.
- Limits: no live PostgreSQL migration or concurrent PostgreSQL stress test, live model accuracy, full-suite, frontend, mailbox, SAP, or accounting-rule validation was performed. Classification and rule definitions remain explicit host/reviewer responsibilities. No commit, push, or deployment was requested for this phase.
- Saved `documentation/PAPER_AGREEMENT_MASTER.md` with external embedding, API examples, authority/version semantics, configuration, deployment requirements, and remaining phase boundaries. Updated the architecture and assessment guides to distinguish this implementation from the proposed general workflow runner.

## Target solution requirements assessment — 2026-10-13

- [x] Read all four requirement PDF pages and inspect rendered diagrams.
- [x] Map every target workflow requirement to implemented orchestration and extraction contracts.
- [x] Cross-check architecture gaps and integration boundaries with focused read-only reviews.
- [x] Deliver the support matrix, recommended extension boundaries, and next implementation priorities.

### Scope

Analysis of the attached target architecture against current source. No application implementation, deployment, or inference quality claims; preserve existing workflows and separate reusable primitives from complete business workflows.

### Review

- Saved `documentation/PAPER_WORKFLOW_ASSESSMENT.md` with requirement matrices for PAPER.73, PAPER.ID, and SAP/payment; a proposed additive architecture; a synthetic case example; implementation priorities; and verified source references.
- Two read-only reviews confirmed that current strategies provide in-process sequence/router/fan-out, while domain repositories, approval/vendor waits, continuous rematching, and email/SAP/payment connectors are absent. Reusable PDF and external-schema extraction supplies the perception boundary.
- Material reuse constraints: Redis destructive dequeue does not recover in-flight work; extraction success is not business approval; the policy reference query lacks tenant and approved/effective-version constraints. General workflow runner/registry remains proposed future work.
- Verification: all four PDF pages were text-read and visually inspected; checked report source links and whitespace. Application code is unchanged. No runtime, live model, mailbox, database, SAP, or accounting-accuracy validation was performed for this assessment.

## Publish extraction changes to origin/main — 2026-10-13

- [x] Inspect pending changes, repository rules, lessons, and refreshed remote history.
- [x] Review changes and validate extraction tests, API integration, dependency metadata, and formatting/types.
- [x] Create focused commits for dependencies, extraction library/examples, API integration, and documentation.
- [x] Push the reviewed commit chain to `origin/main` and verify the remote hash and clean working tree.
- [x] Record the verified publication results in a final documentation follow-up.

### Plan and review

Preserve the current feature branch and all existing changes. Include source, tests, example configuration, and documentation; exclude ignored credentials, uploads, and generated files. Push with a normal fast-forward update after confirming remote ancestry. Record actual verification results and any existing failures below before publication.

- Remote ancestry: refreshed `origin/main` is an ancestor of the current branch; the existing orchestration and checkpoint commits will also become part of main.
- Reviews: two focused read-only reviews found no concrete blocker in the library, API, examples, configuration, or documentation.
- Verification: 163 extraction/API tests passed. A separate legacy extraction/chat/policy/auth/service subset had 123 passes and three failures; all three reproduced at unchanged checkpoint `31d322b` in an isolated temporary export (conversion tests still mock `convert` rather than `convert_hybrid`). Existing API AsyncMock warnings and a legacy JWT fixture warning remain.
- Checks: strict mypy passed for 44 implementation/example files using explicit package bases, silent dependency traversal, and an isolated environment with dependency stubs. Ruff, Black, and isort passed for 55 new implementation/test/example files. Python 3.10 syntax passed for 44 implementation/example files; example JSON/YAML parsed; `uv lock --check --offline` and `git diff --check` passed.
- Credential-pattern review: 154 outgoing files had no unexpected match; the sole match was the deliberately rejected credential-bearing URL on a synthetic `.example` host in a provider test. Ignored environment files and generated artifacts remain excluded.
- Environment: sandboxed verification stalled or failed uv cache permissions; bounded retries outside the sandbox passed. No full-suite, live provider/database, deployment, or frontend validation is claimed for this publication.
- Content commits: `e4c4b61` dependency/schema metadata; `bb86204` reusable extraction, configuration, examples, and tests; `5725c49` authenticated API integration; `8ad52d2` extraction guides, architecture, and verification notes.
- Publication: normal fast-forward push advanced `origin/main` from `68899d4` to `8ad52d2317e3916847ca844c9d24d35d150a3117`. An independent `git ls-remote` confirmed that exact hash matched local HEAD and the working tree was clean. This task-only documentation follow-up records the verified result. The feature branch and existing checkpoint branch are retained.

## Reusable PDF and external schema extraction — 2026-10-13

- [x] Define validated document, multimodal, model, and external schema contracts; write and run failing tests first.
- [x] Implement async PDF reading with full page coverage, native text/OCR selection, image assets, tables, and provenance.
- [x] Implement injectable generation adapters and capability checks without eager ML imports or provider state in results.
- [x] Implement composable document extraction, external-schema field extraction, validation/evidence, and combined extraction.
- [x] Provide composition/configuration and an executable embedding example; keep existing workflow contracts intact.
- [x] Run focused new tests, legacy extraction/chat/policy regressions, formatting/type checks where available, and independent review.

### Scope and verification plan

Implement the public reusable boundary and opt-in integration. Default basic/advanced, chat, and policy workflows retain their entry points and response shapes. Native-text-only extraction needs no model; text-only output may use OCR when requested. External schemas support Pydantic models and validated JSON Schema, with evidence outside the business payload. Tests use generated PDFs and fake models; real inference quality is not inferred from mock tests. Repository async/DI rules conflict with legacy synchronous model APIs, so adapt them at the boundary rather than changing legacy callers.

### Review

- Implemented `src/extraction/` contracts, reader and capability/model ports, document/field capabilities, bounded generation gateway, three adapters, schema validation and async composition. Native-only extraction is independent of ML/application startup; caller schemas own business fields and rules.
- Added authenticated direct-result endpoints `/v1/extract` and `/v1/extract/fields`, host-owned resource ceilings, safe errors, lazy runtime initialization and owned-provider shutdown. Existing document job/pipeline, chat and policy paths retain their response shapes and implementation; no database migrations or UI changes.
- TDD: contract/service/reader/provider/gateway/schema/API tests failed before implementation. Review-driven regressions established failures before rotation, concurrency, schema alias/evidence, resource ownership/cleanup and CLI stdout fixes.
- Verification: 134 new extraction tests passed. Separate existing workflow subset: 197 passed and 3 failed; all three failures reproduced in a temporary export of checkpoint HEAD (tests still mock `convert` although production calls `convert_hybrid`). The subsequently expanded existing API suite passed 29 tests, including 3 new lifespan ownership/error-cleanup cases; that run overlaps the earlier subset.
- Strict mypy passed for 44 new implementation/example files; Ruff passed for all new implementation/test/example files. Black/isort checks passed for 55 new implementation/test/example files. Python 3.10 syntax and function annotation audit passed. `git diff --check` and `uv lock --check` passed with jsonschema added and pre-existing local-vlm lock metadata aligned. Wheel build succeeded; an isolated extracted-wheel smoke test confirmed default YAML and embedding imports without application/ML startup. Documentation JSON and the external invoice example validated.
- Independent review fixed rotated crop/source coordinate mismatch, process-global MuPDF table-state races, configured path typing, schema traversal/ref resolution, ungrounded evidence, native structured-output wiring, and API budget bypasses.
- Limits: no live provider accuracy, live database, full-suite, deployment or frontend validation claimed. Complex negation/exclusive/conditional schemas may fail partial-candidate validation; final original schema validation remains mandatory. Evidence establishes literal source traceability, not semantic correctness. Assets are bounded inline PNGs; PDF work is serialized per process, with active off-thread work finishing after caller cancellation.
- Work is on `codex/reusable-pdf-extraction`; the pushed pre-refactor checkpoint is retained. Publication status is tracked in the `Publish extraction changes to origin/main` section above.

## Model agnostic workflow abstraction design — 2026-10-11

- [x] Review existing extraction, model, worker, and chat boundaries and session lessons.
- [x] Cross-check model and capability contracts with two focused read-only architecture reviews.
- [x] Define typed capability contracts, model ports, workflow composition, and external embedding.
- [x] Record a concrete invoice example and an incremental migration with acceptance checks.
- [x] Verify the proposal against current source and deliver the design.

### Scope

Architecture proposal and implementation plan. Application implementation begins separately with failing contract tests; this task does not refactor the runtime.

### Review

- Saved the proposed contracts, module layout, invoice bindings/results, external host example, extension procedure, failure/resource rules, and staged acceptance checks in `documentation/WORKFLOW_ABSTRACTION.md`.
- Two read-only architecture reviews cross-checked current source. Follow-up review corrected invoice provenance bindings, shared binary asset resolution/lifetimes, cancellation propagation, and diagnostic persistence before optional workflow exposure.
- Verified two Python examples with syntax parsing, the YAML and JSON examples with parsers, source link targets, and source chunk provenance references. `git diff --check` passed.
- This is a design deliverable; runtime acceptance tests remain implementation requirements. Changed documentation/task tracking only; no model, database, or live workflow execution was required or claimed.

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
