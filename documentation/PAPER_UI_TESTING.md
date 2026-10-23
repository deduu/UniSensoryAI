# Test PAPER agreements and invoice cases

Open [PAPER review](http://localhost:5173/paper) to upload PDFs, review extraction results, and prepare editable agreement or invoice drafts. Manual forms and JSON imports remain available. [Swagger UI](http://localhost:8010/docs) exposes the same queued extraction, approved agreement master, reconciliation service, and persisted review decisions. The web app starts manual drafts with empty document fields and has no synthetic example loaders or approval autofill controls.

## Saved document drafts and case readiness

Invoice document review now saves independently of reconciliation. The normal UI flow is **Review document → Save reviewed version → Prepare case → Select documents and confirm contract → Check readiness → Run reconciliation**. Agreement draft/approval and existing case correction/decision workflows remain available.

1. Open **Document inbox**, select the invoice upload, then **Review / edit invoice**. Review the fields beside the original. Required/conditional/optional badges describe case prerequisites; an incomplete document can still be saved. Source vendor/store/contract IDs remain unknown when absent from the PDF; case assignment is separate.
2. Enter a review/change reason and choose **Save document draft**. To make the document selectable, explicitly check the source-review acknowledgement and choose **Save reviewed version**. This records the authenticated reviewer and time, without approving payment. **Create revision** appends a version and requires a fresh review; **Document version history** retains earlier snapshots, warnings and evidence.
3. Reopen through **Saved document drafts and reviewed versions**. Search by document reference and filter by role/review status. Choose **Prepare case** on a reviewed rent invoice. For other roles, **New document draft** supports tax invoice, utility statement and supporting document schemas. Enter actual source-supported data and retain its source ID; the PDF upload extraction picker still supports agreements and rent invoices.
4. Confirm the exact approved contract using the existing candidate evidence comparison. Under **Add reviewed supporting documents**, search reviewed drafts by role and explicitly add the exact versions for this case. Duplicate draft versions and duplicate source IDs are rejected. One case has one primary invoice and up to 99 other documents, with a maximum of 100 in total.
5. Choose **Check readiness**. Missing prerequisites appear first, with their field, reason and source shortcut. Completed, optional and not-applicable checks remain collapsed. Checking readiness does not write an invoice case or an assessment. Changing selected documents, allocation or contract requires a fresh check.
6. **Run reconciliation** becomes available only when readiness permits it. The backend re-resolves exact reviewed versions and current approved authority before saving through the existing case workflow. The saved case retains each selected draft ID/version/source/reviewer/time. Matching discrepancies are results to review, not evidence of a missing prerequisite; readiness alone does not approve an invoice. AP decision remains separate.

Existing raw package endpoints continue to accept manual integrations, including incomplete cases. Their caller-supplied document-draft review references are discarded: use `/cases/from-drafts` to establish verified saved-document provenance. A manual correction preserves earlier case history and saves its supplied fields as a new manual snapshot.

The additive migration `a1090c3d67ef` creates document draft headers and immutable versions. Apply `alembic upgrade head` in the configured backend environment (or `docker compose exec -T api alembic upgrade head`). The active local stack has this migration applied. Do not recreate volumes or remove extraction artifacts.

The reviewed development invoice now has draft v1 and reviewed v2. Currency IDR in v2 was checked against page 1; monetary values, evidence, original extraction and missing source dates/IDs were retained. The readiness check still requires tax evidence and approved service-period coverage. No new real reconciliation case, AP approval, extraction call or extraction cost was created for this verification.

### Configure field requirements

Open **PAPER review → Settings → Field requirements** to configure rent invoice, tax invoice, utility statement and supporting document fields. Choose a document type, find a field, then select **Required**, **Optional** or **Conditional**. Conditional requirements can depend on whether a field has a value, is missing, or equals a typed value in a selected document. Supply the requirement reason and save the settings. Changes are shared within the current tenant, stored on the backend and take effect without restarting. Editing requires the existing configured AP reviewer permission; other users can inspect the settings.

Saving records an immutable policy revision with reviewer and time. A conflicting edit requires reloading the latest settings before retrying. Field labels, case readiness and actual matching use the same policy. Existing local source edits stay open, readiness must be checked again, and old assessments must be reassessed before a new decision. Saved document values, assessments and recorded decisions are not rewritten. Contract master publication requirements remain a separate policy.

**Use deployment defaults** stages removal of all tenant field overrides. Review the resulting fields, then select **Save field requirements** to apply the reset. **Discard changes** restores the currently saved policy.

Apply migration `b9040a7fe213` before using the new settings endpoint. `GET /v1/paper/field-requirements` returns the effective field catalog, deployment defaults, raw tenant overrides and revision. `PUT` accepts `expected_revision` and a complete replacement of the sparse tenant `requirements` overrides. Inherited fields must stay out of that override list: explicit requirements also govern document presence and approved tax substitutions. Tenant and reviewer identity come from authentication. Conditions use supported scalar fields and typed equality values, rather than executable expressions.

Deployment defaults remain in `configs/paper_reconciliation.yaml` (selected by `PAPER_RECONCILIATION_CONFIG_PATH`), or validated `ReconciliationSettings` supplied by an embedding host. Before a tenant saves settings these defaults apply unchanged. Deployment YAML changes require a backend restart and a new policy version; the effective tenant policy also binds the deployment configuration so existing assessments cannot silently retain old accounting behavior.

For example, add these entries alongside the existing policy:

```yaml
policy_version: "3" # use your own versioning convention
field_requirements:
  - role: rent_invoice
    field: due_date
    requirement: required
    reason: The host requires a reviewed payment due date.
  - role: rent_invoice
    field: vat_amount
    requirement: optional
    reason: Legacy signed-tax invoices can omit separate VAT components.
  - role: supporting_document
    field: reference_number
    requirement: conditional
    reason: A withholding certificate needs its actual certificate reference.
    when:
      role: supporting_document
      field: document_type
      operator: equals
      value: withholding_certificate
```

Supported predicates are `present`, `absent` and typed `equals`; presence predicates omit `value`. Requirement/condition fields must be known scalar fields from the selected PAPER schema. Monetary equality uses exact decimal semantics. Conditions on the same document role apply separately to each selected document; cross-role conditions inspect selected documents. An active required/conditional field can also require its document role. Up to 128 unique role/field declarations are allowed; unknown fields, invalid predicates and duplicate declarations are rejected at configuration load.

Optional presence never waives approved coverage, installment/withholding component requirements, or AP authorization. Existing required document roles, supporting types and approved tax-substitution rules still apply. Authorized reviewers edit field-presence policy through the separate PAPER Settings tab; case review itself remains governed by the effective saved policy. These contracts and pure rules use no extraction model/provider.

For external systems: `/v1/paper/document-drafts` creates/lists drafts, `/{id}/versions` appends/lists versions, and `/{id}/versions/{n}` reads an exact snapshot. POST `/v1/paper/cases/preparation/readiness` or `/v1/paper/cases/from-drafts` with assigned `identity`, an `invoice` reference `{draft_id, version_number}`, optional arrays `tax_invoices`/`utility_statements`/`supporting_documents`, and the selected `association` `{agreement_id, version_number, reason}`. Optional `review_context` retains a separately reviewed installment allocation; never replace unknown source dates with guessed allocation dates. An existing case revision supplies both `case_id` and `expected_version`.

## Navigate the guided workspace

The workspace opens on **Cases**, with searchable invoice cases, their current status, confirmed contract version and next action. Open a case to see its invoice, contract and supporting documents together, then compare values, inspect findings, correct/reassess and record a separate AP decision. **Review linked contract vN** opens that exact version inside the case; **Back to invoice and matching** returns to the same invoice workspace. Source shortcuts open the original PDF without replacing the saved case.

**Document inbox** shows uploaded documents, extraction status, saved workflow links and next actions. Search and status filters run on the server before pagination; archived attempts remain available through the archive filter. A saved workflow shortcut opens the linked version instead of creating another draft. If a source belongs to multiple saved records, choose the intended record explicitly. **Review original** opens extraction review; **Review / edit agreement** or **Review / edit invoice** prepares a local draft. Open **Extraction options** to change text/multimodal mode and **Extraction details and downloads** for full text and result downloads. Desktop review shows original and extracted content together; compact layouts provide **Original / Extracted** controls.

**Contracts → Rent Agreement Master Repository** lists saved masters, approval status and linked invoice counts. **Review contract** opens its saved terms; **Linked invoices (N)** filters Cases by confirmed association to that master. Legacy assigned-identity links are labelled separately and are not counted as reviewer-confirmed associations. The case keeps its selected version even if a newer agreement draft exists.

Switching tabs preserves unsaved edits while this page stays open. Opening a different saved record or extraction draft while an editor is active offers a keep/replace choice. Reloading or leaving the page still requires saving first. Tabs support arrow keys, Home and End. Older walkthrough sections below use **Documents**, **Agreement master** and **Invoices** for the same workflows now located in **Document inbox**, **Contracts** and **Cases**, respectively.

Original and extracted page controls share one page selection. **This page** shows the selected page's stored text, tables and exactly linked canonical values; next/previous actions on either side update both sides and reset their scroll positions. Missing extraction or absent page citations are stated explicitly, with no content borrowed from another page. **All fields** shows the complete saved extraction and citations. Editable drafts open in **Edit all fields**; changing a source page opens page review, and returning to the editor preserves unsaved inputs and unapplied JSON. Page-specific draft values retain earlier evidence, so source verification is still required after edits. Short values use multiple columns when space permits; long prose and structured values retain full-width space.

**Review tools** stays at the bottom right while scrolling a document or draft. **Evidence**, **Review issues**, and **Sources** open a non-modal inspector with its own scroll area, so the long form no longer has an evidence footer to scroll to. Search evidence by field path or quoted text; search issues by code, message or field. With an original attached, **Current PDF page only** filters citations to exact page links and issues to current-citation pages, retaining issues with no resolved pages. Clear the filter to see unresolved citations too. **Sources** retains document references and explicitly states when no original preview is attached. Close the inspector with its close button or Escape; focus returns to its toolbar.

Each extracted field and ordinary schema editor field has **Evidence** and source shortcuts. **Evidence** opens only that field's exact and descendant citations without moving you away from the field. A single-page **source icon / p. N** opens the original and its evidence together. **N pages** expands every linked page button, including citations attached to nested values. Citation cards also expose all their linked pages. **Back to field** closes the inspector, reveals **All fields / Edit all fields**, and restores the field and scroll position. Shortcuts preserve unsaved controls and unapplied JSON; on compact screens they reveal **Original** when opening a page. **No linked source** opens evidence details without guessing a page. Evidence from other documents and ambiguous source IDs remain unlinked. Edited values retain earlier citations and still require source verification.

The **Rent Agreement Master Repository** contains saved drafts and approved versions. A local editor is labelled **Unsaved draft · local changes**; it is not yet a saved record. **Save draft version**, at the editor's top and bottom, validates required identity/effective-date/source/reason inputs and saves a version. The saved version then exposes its separate approval form and version history. Only an approved version can be used as the authoritative invoice reference.

Agreement terms are grouped into sections. **Field guidance**, source references, and exact JSON expand on demand. Invalid controls inside a collapsed section reopen that section and receive focus. Warnings, source discrepancies, installment conditions, and explicit AP acknowledgements remain available; nothing is automatically acknowledged. **How it works** explains the flow, and **Workspace** shows reviewer access and the active policy.

On desktop, both review panes stay within the viewport in **All fields** as well as page review. Scroll the fields independently while the PDF and the field toolbar remain available. In Agreement master, **Jump to** opens overview, parties, contract terms, payment rules, approval, or history without scrolling through every section. Saved terms are readable values, including nested objects and full clauses; exact JSON remains available on demand. **Documents → All fields → Find a field or value** searches names and nested values without changing extraction data.

Opening field **Evidence** shows the current value with its retained source quotes. A page shortcut opens the same original PDF; on compact screens it closes the inspector so the PDF is unobstructed. Open **Evidence** separately to read the quotes. **Back to field** restores the selected field. In revisions, string lists use individual clause editors with per-clause citations. Add/remove and unknown/empty-list choices are explicit. Unapplied advanced JSON edits disable competing clause edits and prevent native form submission until applied or discarded. Verify that an edited clause survives a page change and return to **Edit all fields**; cancel a test revision to avoid saving it.

The approval form calls the API's `rule_set_id` **Accounting policy reference** and `rule_set_version` **Policy revision**. Enter the organization's approved accounting-classification reference and revision explicitly. These are saved audit references, not extracted terms or a selector for executable invoice matching rules. The API validates nonblank reference structure; it does not resolve an accounting policy catalog or verify its contents. The configured invoice reconciliation policy shown under Workspace is separate and must not be copied as a default. Earlier saved approval values remain unchanged. Required inputs and party/warning acknowledgements are preserved.

Use **New draft** for an agreement and **New document draft** in Document inbox for an invoice or supporting document. Save reviewed versions before preparing a new case. The existing manual case correction form and raw package API remain available for older integrations. Agreement classification, policy references and approval reasons require reviewer input. Subtle stage/disclosure transitions and loading indicators respect the operating system's reduced-motion preference.

## Current review issues and historical diagnostics

1. Open **Agreement master**, select the saved version, and use **N need review** or **N history** above its PDF. **Review tools → Review issues** opens **Needs review** by default. **History** and **All** retain access to the complete log; search and current-page filters apply within each view.
2. Each entry shows its current assessment reason, linked current source pages, **View current field evidence**, and its **Exact retained entry**. Historical entries use neutral styling. Upload lists label their original counts as **log entries**, since a saved extraction attempt does not know the current draft's review state.
3. A rejected-citation diagnostic is historical only when this exact field has a current value and all its current citations resolve uniquely to the attached document and contain a literal quote in stored text. Foreign, missing, ambiguous or nonliteral evidence stays in **Needs review**. Missing originals keep citation verification unresolved. Aggregate review items can link every child citation; child evidence cannot retire a leaf citation failure.
4. Revision and scope notices describe earlier events. Narrative, party-role, incomplete-field and unknown diagnostics remain review requirements. Filled values do not automatically resolve them. A matching quote establishes traceability, not the correct party, complete conditions or semantic accuracy.
5. Unsaved edits reopen affected rejected-citation items against the saved draft/extraction baseline. Cancelling restores the saved projection. The assessment runs locally without a model and changes neither stored warnings nor approval policy. Reviewer acknowledgements remain initially unchecked and still cover the entire retained log.

Agreement 65 v5 currently projects **19 review items and 30 historical entries**, from 49 immutable diagnostics. History contains 23 rejected earlier citations whose current citations now pass literal checks, five candidate-revision notices and two correction/scope notes. Needs review contains 12 narrative checks, six incomplete-field decisions and one party confirmation. These are not 19 proven extraction errors: assigned vendor/store IDs require external confirmation, fixed-rent classification lacks its own citation, currency has a traceable Rupiah citation, and the two null revenue-share fields may be inapplicable. Some narrative candidates do contain changed or omitted conditions, so complete-clause review remains necessary before publication. Earlier versions and the effective approved v4 are unchanged.

## Readable text and legal party review

1. In **Documents**, open a saved extraction and choose **This page → Readable**. Recovered Markdown becomes paragraphs, emphasis, lists and tables. **Raw text** exposes the unchanged transcription. Document HTML, links and images remain inactive. Narrative strings and clause arrays in **All fields** have readable presentation and exact JSON; short scalar values and evidence quotes stay literal.
2. In **Agreement master**, open a saved version. Its original loads through exact document identity; multiple originals require explicit selection. **Legal parties and representation** separates landlord, tenant, representatives and extracted supplier from the assigned vendor ID. Attribute and aggregate shortcuts retain all cited pages. Missing sources remain explicit.
3. Choose **Create revision** to correct names, roles, source wording and representation steps. Supplier name remains independently editable in **Parties and premises**. Add/remove entries in **Additional source attributes → Extensions**; use the existing agreement JSON import when correcting qualified citations. Source navigation preserves unsaved edits. **Save draft version** appends an unapproved snapshot.
4. Inspect complete party clauses and representation chains. Structured party versions require the separate, initially unchecked **I verified the legal landlord…** acknowledgement and ordinary warning review. Acknowledgement cannot bypass role conflicts, a tenant selected as supplier, missing citations or unresolved representation. Saved party metadata cannot be removed to bypass the gate. Historical snapshots retain their existing approval behavior.

New agreement extractions run a dedicated party-role pass through the configured field profile. The generic extraction service remains independent of PAPER and providers; invoice processing retains its existing path. Optional typed metadata lives at `terms.extensions.party_roles` (version `1`): `parties[].name`, `role`, `source_role`, and `representatives[]` (`name`, `represents`, `capacity`). Unknown values remain explicit. The protocol version receives no invented PDF citation. Pure checks establish consistency, citation support and declared chain connectivity; semantic completeness still requires human review.

Embedding hosts can inject `BasePartyRoleValidator` into the processor/master service or call `load_party_role_settings`. The application uses the same optional `PAPER_PARTY_ROLES_CONFIG_PATH` YAML for extraction and approval; packaged defaults support explicit Indonesian and English labels. No model or sample party name is hardcoded. The additive decision flag is `acknowledge_party_roles: true`; omitted/false flags preserve legacy approval serialization. No migration is required.

Targeted repairs may reuse hash-verified OCR and prior reviewed terms, explicitly recording scope and source/version lineage in a new worker attempt. This does not mean every field was freshly re-extracted. Source-reviewed draft corrections remain separate from automatic artifacts. Earlier uploads, warnings, versions and approvals remain available; the prior approved version remains effective until an authorized reviewer publishes a correction.

## Compare an invoice with its approved contract

1. In **Document inbox**, reopen your contract extraction, select **Review / edit agreement**, verify the values and supporting evidence, **Save draft version**, and approve the saved agreement in **Contracts**. If a saved workflow link is already present, open that record to continue instead.
2. Reopen your invoice extraction and select **Review / edit invoice**. Save a reviewed document version, then **Prepare case**. Review contract candidates and source evidence, select reviewed supporting documents and any source-supported installment allocation, and confirm the association with a reason. **Check readiness**, resolve prerequisites, then **Run reconciliation**.
3. The saved case opens **Contract and invoice comparison**. Existing records open from **Cases → Find an invoice case**, or **Contracts → Linked invoices (N)**. The case list collapses to give the comparison the available width. **Case documents** links both originals and the exact confirmed contract, with direct jumps to findings, AP decision and version history.
4. Compare **Contract expectation**, **Invoice value**, and **Comparison / saved result**. **Field values** shows literal equality/difference or missing values for invoice identifiers, currency and bank account. Linked identities are reviewer-assigned and cannot fill missing invoice fields. **Saved result** retains the server findings independently. The reference is the exact approved agreement version recorded in that assessment, even after a newer agreement is created or a different agreement is selected elsewhere. Overall assessment and later AP decision remain separate.
5. Click **p. N** beneath either value to inspect the corresponding original PDF and field quotes alongside the table. Every uniquely resolved source page is available. Switch **Contract / Invoice**, change pages, zoom, or open the original PDF. A contract with multiple source documents also exposes a document selector. **Back to comparison row** restores the triggering control; on compact screens the reader is a modal dialog with Escape support and keyboard focus containment.
6. Use **Needs attention** to narrow the table, expand individual findings, and inspect **Additional findings** for attachment or custom-rule findings that do not belong to a displayed primary-invoice row. **Correct / reassess** opens the existing correction workflow. All original findings and AP review/approval controls remain available below.

The table presents saved server findings; **No finding reported** is not a positive assertion that every field was evaluated. Unknown fields and unavailable originals remain explicit. An absent or invalid installment selection never substitutes annual rent for the expected cash amount. Source service dates remain separate from human-reviewed allocation dates. Structured VAT/withholding invoices and legacy signed-tax invoices retain their own arithmetic descriptions. Decimal values remain exact stored strings; this presentation does not recalculate financial decisions or call a model.

A confirmed selected contract can be shown as **reference only** while service coverage is unresolved. **Values equal** may still appear for simple displayed values such as currency and account number; it does not establish contract coverage or an assessed match. Missing source identifiers show **Invoice field missing**, and saved blocking findings show **Issue reported**. The overall incomplete assessment and coverage warning remain visible until the invoice is corrected and reassessed. Amount, tax, coverage and payment-condition checks do not gain a literal equality grade.

Originals are resolved through the additive tenant-scoped `GET /v1/paper/extractions/by-document/{document_id}` endpoint. It verifies canonical source identity, supports historical uploads lacking identity metadata, and bounds artifact reads and lookup time. Missing or unreadable sources leave saved values and findings visible; **Reload sources** retries without changing the case. This addition needs no migration and creates no example records.

## Start the local stack

From the repository directory, keep the existing `.env` and run:

```powershell
docker compose up --build
```

Compose starts PostgreSQL, Redis, the API at `http://localhost:8010`, and the web app at `http://localhost:5173`. Existing database migrations run before API startup. The PDF upload/history addition reuses the existing ingestion and document tables and introduces **no new migration**. Keep the same Compose project and its named volumes; `data/` stores the uploaded sources and extraction artifacts through a bind mount. Do not remove database volumes or uploaded files when you want to retain history.

Docker selects `QUEUE_BACKEND=redis` unless explicitly overridden. Redis stores queue entries; background worker coroutines run **inside the API process**, rather than in a separate worker container. `WORKER_CONCURRENCY` controls the Redis worker count (default `4`), while extraction profiles bound model concurrency separately. Queue workers dispatch PAPER extraction through its workflow handler; existing Dashboard processing retains its own handler. Worker execution and upload/result history are separate concerns: PostgreSQL stores the tenant-scoped history, and private files retain the originals and detailed results.

Authentication and reviewer permissions follow backend configuration. The configured local `dev-user` reviewer has an allowed role; other deployments need their own authenticated reviewer. All PAPER reads, writes, and original PDF links use the same backend selected in the app settings as the shared upload history.

### Configure OCR and field models

Compose selects `configs/extraction.yaml` through `EXTRACTION_CONFIG_PATH`. Configure the deployment environment before starting the API:

```dotenv
EXTRACTION_BASE_URL=https://your-compatible-provider.example/v1
EXTRACTION_MODEL=your-vision-capable-model
EXTRACTION_API_KEY=your-private-key
EXTRACTION_WORKFLOW_TIMEOUT_SECONDS=1800
```

Keep real credentials in the deployment environment, never in source files, document forms, or extraction payloads. The endpoint ends at its API version prefix, such as `/v1` or `/openai/v1`. Compose can also take the endpoint and credential from existing `OPENAI_API_BASE` and `OPENAI_API_KEY` values. The configuration binds separate `vision` and `fields` profiles; `vision` must support images for scanned-page OCR. Copy `configs/extraction.example.yaml` to select different models/endpoints for those roles. Other protocols can use the reusable extraction provider interfaces without changing PAPER contracts or the UI. See the [extraction configuration guide](EXTRACTION_API.md#configure-or-replace-a-model).

Queued PAPER document extraction uses the validated `EXTRACTION_WORKFLOW_TIMEOUT_SECONDS` budget (default 1800 seconds, maximum 3600), allowing OCR across long scanned PDFs. Each model call still has the configured 60-second inference timeout. The reusable library's default remains 300 seconds. A normal API shutdown requeues interrupted PAPER work; Redis list entries and saved results persist across restarts. Abrupt process loss after a worker consumes a job still requires interrupted-job recovery; the current Redis backend does not implement acknowledgement leases or exactly-once processing.

Environment changes require recreating the API container; Python/configuration changes require an API restart. Native-only extraction in a library host does not need a model, but scanned PDF OCR and schema fields need configured profiles. Missing profiles or provider failures remain visible as failed jobs or retained partial results with warnings.

## Test PDF upload, extraction, and editable drafts

1. Open **PAPER review → Documents**. Select a PDF, choose **Rent agreement** or **Rent invoice**, then open **Extraction options** to select **Text with OCR** or **Text and visual content**. Both modes can OCR scanned pages; multimodal output also retains visual assets. Click **Upload and extract**.
2. The upload is saved and queued. Open its card in **Recent uploads**. Expect `pending`, then `processing`, then `completed` or `failed`. Active cards refresh automatically. Long scanned agreements require OCR across their pages and can take longer than a single-page invoice.
3. Inspect **Open original PDF** and **Review tools → Evidence / Warnings / Sources**. **Extraction details and downloads** retains **Full extracted text**, **Download text**, and **Result JSON**. Evidence retains field paths, source block IDs, and exact quotes. Warnings can refer to a page or field. Structural validation and literal quotes do not guarantee that a model chose the correct business role or interpreted a payment condition correctly; compare important terms against the source. Viewing or filtering warnings does not acknowledge them for agreement or invoice approval.
4. For a result with fields, click **Review / edit agreement** or **Review / edit invoice**; **All fields** also has a **Review / edit** shortcut. The matching editor opens directly with a local copy of values, evidence and warnings. With an editor already open, explicitly choose **Replace unsaved draft and review** / **Replace unsaved package and review**, or **Keep current draft** / **Keep current package**. Nothing silently overwrites the current editor. Reopening review is an explicit new request; saving or cancelling does not automatically reload an earlier extraction.
5. Review and edit the fields. Missing vendor/store IDs, contract numbers, and service dates stay unknown; obtain them from verified sources or the consuming system. Invoice dates are not service dates. Agreement effective dates initially follow extracted contractual rent dates and need review; they do not establish an accounting commencement decision. Agreement drafts retain `source_document_ids` and document-qualified evidence. Invoice drafts retain `source_document_id`, evidence, and warnings. Document, field, and workflow warnings all carry into the draft.
6. Click **Save draft version** for an agreement. It appears as a saved draft in the **Rent Agreement Master Repository**; separately review and approve that version. For an invoice, supply the remaining identity and supporting documents, then click **Reconcile package** to save and assess it. AP approval remains a separate authorized action. Extraction does not create an approved master, fabricate tax documents, post to SAP, or determine a lease classification.
7. Reload the page or return later. Reopen the upload/result from history; original artifacts and model output remain unchanged by draft edits. **Unsaved form edits are local to the open editor and do not survive reload.** Save the agreement draft or invoice case to persist those edits. A saved extraction can always be copied into another review draft.

A `completed` job may have `extraction_status: "partial"`. If OCR succeeded but field extraction failed, full text and diagnostics remain available with `fields: null`. **Review / edit agreement** (or invoice) starts an empty editable draft retaining its source ID and warnings. Enter fields from the source manually; no canonical values are invented. A wholly `failed` job exposes **Retry extraction**. Retrying creates a new attempt and retains the earlier failed history entry. Partial results can be uploaded again if a new extraction attempt is needed.

### Find earlier uploads and extracted files

- **PAPER review → Documents → Recent uploads** lists persisted PAPER attempts, including pending, failed, and completed uploads. Use **Newer / Older** for earlier pages, **Refresh extraction history** to fetch changes, and the result refresh button to reopen current output. A direct link has the form `/paper?extraction=<job_id>`.
- **Upload history** in the sidebar lists server-backed jobs across sessions. PAPER rows are labeled, and their details link to **Review / retry in PAPER**. Accepted uploads and retries refresh the shared history automatically; active jobs are polled. The list hydrates all server pages rather than stopping at the API's default page size.
- **Documents** lists recovered document text after processing. Use its search, filters, pagination, preview, and text download. Originals and complete PAPER JSON/evidence are available in the PAPER result view.

These views are tenant scoped and use server history rather than storing document contents in browser session storage. Switching accounts, tenants, or API hosts clears the visible cached history. Failed uploads with no recovered document still appear in upload history rather than the completed document list. Queue workers alone do not provide a browsable result archive; these views read the persisted job/document records and private artifacts.

At the 2026-10-15 verification checkpoint, the supplied one-page scanned invoice completed through the queued extraction path with 10 evidence quotes. The supplied agreement completed OCR across all 38 pages (58,680 text characters); field extraction returned a partial result with 15 warnings and no verified field quotes. Its fields require source review. The original 300-second whole-document deadline was insufficient; the queued host now uses the configurable 1800-second budget. A subsequent invoice upload was also submitted through the browser and completed. These checks establish execution and retained diagnostics, not complete extraction accuracy or accounting approval.

At the subsequent evidence-repair checkpoint, fresh agreement OCR completed all 38 pages with 59,569 characters. A new saved field attempt, `676e7411-383a-4be4-918c-553491503193`, reused that unchanged hash-verified OCR through an injected document capability and the normal worker/result storage. It returned 29 literal citations and zero `missing_evidence` warnings. **Original-PDF acceptance still failed**: the model selected the tenant as landlord, left pricing type unresolved and omitted deposit prerequisites. Its 46 raw diagnostics remain retained (42 unique issues in the UI). A literal quote match proves occurrence in OCR, not correct party roles, complete conditions or field-value support. Keep automatic results partial and distinguish any separately corrected review draft from unassisted model output.

A separate, explicitly **agent-assisted and unapproved** source-corrected candidate is preserved locally in ignored `data/runtime/paper-real-sample/agreement-source-reviewed-candidate.json`; `agreement-source-reviewed-draft.json` is its validated `AgreementDraft`. Its 39 reviewed quotes exactly occur in the retained OCR blocks, and 14 primary source/unknown-preservation checks pass. Selected payment, deposit, renewal, termination, force-majeure and return terms were compared with original page images; this is not a complete legal abstract or human approval. Bank details and external vendor/store IDs remain null, and the source-stated IDR 3 arithmetic discrepancy is retained. The automatic attempt is unchanged.

Corrected values were loaded into the open, **unsaved** agreement form for side-by-side inspection. That form retains historical automated evidence; the separate reviewed draft file contains the replacement reviewed evidence and labelled historical diagnostics. The version reason records this distinction. Do not treat its old quotes as verification of edited values. Full agreement JSON import still requires external canonical identity, so obtain the actual host identifiers before wrapping/importing or saving this real sample. The UI's ordinary extraction-to-draft handoff permits missing identities for review and does not save or approve them.

## Test manual forms and JSON through the web app

Use the Docker startup above, or the optional manual startup below. These steps use your own verified documents and host identifiers.

1. Open **PAPER review → Agreement master → Browse saved agreements and versions → New draft**. Enter the agreement identity, source references, dates, terms, and change reason, or import your typed agreement JSON.
2. Review the terms and click **Save draft version**. In **Review and approve this version**, enter the classification, accounting policy reference, and review reason from your approved policy. Acknowledge retained extraction warnings explicitly if required, then approve the exact version.
3. Click **Use for invoice**, then **New invoice package**. The selected agreement supplies only its identity; invoice document fields start empty. Supply the actual invoice fields and add required tax or supporting documents from verified sources. **Advanced package import → Advanced package JSON** accepts a complete typed package.
4. Click **Reconcile package**. Inspect the saved assessment, its findings, and the exact approved reference. A complete supported package can be **Matched**; absent required documents remain **Incomplete**, and structural blockers prevent approval.
5. Use **Correct / reassess** to supply missing verified documents or correct fields, then **Save correction and reassess**. Earlier versions remain in history. No control creates synthetic tax documents from invoice values.
6. An authorized reviewer records a decision reason and only policy-permitted exception acknowledgements before **Approve invoice** or **Reject invoice**. Reusing a claimed vendor/invoice number in another package produces **Duplicate** and disables approval.

Use **Create revision** for agreement corrections and **Correct / reassess** for invoice corrections. Canonical identity is fixed during revision. **Approved reference on a date** checks which approved version applies; a newer draft does not replace approved authority. Reopen records from the left queue to verify persistence, and use the history controls for earlier versions. After a stale-version/reference error, reload the latest case and reassess before another approval attempt.

Ordinary fields come from the backend's external schemas. Optional JSON editors preserve extensions, evidence, and warnings; click **Apply** before saving structured edits, or **Discard edits**. Importing a package replaces its document collections, including clearing omitted optional roles. Decimal amounts and bank accounts remain strings. Unknown fields can stay empty for reconciliation to flag; publication has separate completeness checks.

Existing **Dashboard** extraction, manual PAPER forms, and typed package/agreement JSON imports remain available alongside the new PAPER upload flow. Email and SAP connectors remain subsequent work.

The 2026-10-16 local cleanup removed four generated demo agreements and seven demo invoice cases, including their test versions, approvals/decisions and duplicate claims. Agreement **65**, its four versions and approval were preserved because it references the supplied real PDF, despite its temporary `test` vendor/store identifiers. All 19 retained upload/result files and unrelated database tables were verified unchanged. An ignored local recovery export under `data/runtime/paper-demo-backup-20261016T165543344938Z.json` was validated by restoring its rows inside a rolled-back savepoint. Development-only JSON fixtures remain in `examples/paper/` for isolated testing, without web controls that load or approve them.

## Optional manual startup and Swagger sign-in

Use your configured development database, deployment credentials, and extraction profile path. Apply existing migrations and start the API from the repository directory:

```powershell
uv run alembic upgrade head
$env:EXTRACTION_CONFIG_PATH = "configs/extraction.yaml"
uv run python -m src.api.server
```

Run `npm run dev -- --host 127.0.0.1` in `frontend` for a manually started web server. Manual API startup uses the in-memory queue by default; select `QUEUE_BACKEND=redis` and a reachable `REDIS_URL` to use Redis workers. Docker's Redis is internal by default, so a manually started API needs an explicitly reachable Redis endpoint. Configure the same model environment variables as above. Avoid running manual servers on the Docker stack's occupied ports.

Open `http://localhost:8010/docs`. Expand an operation, click **Try it out**, replace the example body, and click **Execute**. Read the actual **Response body** and **Response code** below the form.

With authentication enabled, sign in through your configured Google/GitHub login first using the same backend hostname. The browser's existing session cookie authenticates same-origin Swagger requests. If your deployment supplies a valid bearer token, Swagger's **Authorize** button accepts that token instead. Approval needs a persisted user in the current tenant whose role is `admin`, `accountant`, or `ap_approver` under the default policies. OAuth creates `member` users; your trusted administrator must assign the intended review role. A synthetic identity with authentication disabled can create drafts, but cannot approve without a persisted allowed role.

The migration chain ends at `dc728f04a912`, adding agreement and invoice-case storage. The commands above change the database you configure. Implementation verification used offline migration generation; the subsequent local startup on 2026-10-14 applied all migrations to PostgreSQL and verified the seven PAPER tables.

For the local setup completed on 2026-10-14, the API runs on `127.0.0.1:8010` with authentication disabled. At the user's explicit request, the persisted `dev-user` account in the development tenant has the `accountant` role. You can execute the Swagger examples directly without an OAuth login in this configuration. A rollback-only PostgreSQL check verified agreement approval, invoice matching, and AP approval; its temporary business records were removed by transaction rollback.

## Create and approve the reference agreement

**Development-only Swagger examples:** the JSON fixtures and synthetic approval reasons in this and the following test sections are for an isolated development database. Importing or submitting them creates new test records; do not use them as real agreement, tax, invoice, or accounting evidence. The normal web flow above uses your own verified inputs.

1. In `GET /v1/paper/schemas`, execute the request. You should receive five version-1 external schemas.
2. In `POST /v1/paper/agreements`, paste [agreement.json](../examples/paper/agreement.json). Expect **201** and `status: "draft"`. Copy `agreement_id` from the response.
3. In `POST /v1/paper/agreements/{agreement_id}/versions/{version_number}/approval`, enter that ID, version `1`, and this body:

```json
{
  "classification": "non_psak73",
  "rule_set_id": "demo-accounting-policy",
  "rule_set_version": "1",
  "reason": "Reviewed synthetic UI test agreement"
}
```

Expect **200** and `status: "approved"`, with the reviewer and approval time recorded. This classification is synthetic test data, not an accounting conclusion. The sample's approved `extensions.fixed_rent_basis: "monthly"` explicitly establishes how to compare its fixed amount.

4. In `GET /v1/paper/agreements/approved`, enter vendor `DEMO-VENDOR`, store `DEMO-STORE`, contract `DEMO-RA-2026`, and `as_of: 2026-06-01`. Expect that approved version. Before approval, this lookup returns **404**.

On another test run, reuse the stored agreement or change its contract number in both sample files; creating the same tenant/business identity again returns **409**.

## Reconcile a complete invoice package

In `POST /v1/paper/cases`, paste [invoice_package.json](../examples/paper/invoice_package.json). Expect **201**, `status: "matched"`, no findings, and an agreement reference pointing to the approved version. Copy the returned `case_id` and `version_number`.

In `POST /v1/paper/cases/{case_id}/versions/{version_number}/decision`, enter the ID and version `1`, then submit:

```json
{"action": "approve", "reason": "Reviewed complete synthetic invoice package"}
```

Expect **200**, `status: "approved"`, and a decision containing the persisted reviewer identity and UTC time. `GET /v1/paper/cases` lists current versions; `GET /v1/paper/cases/{case_id}/versions` retains historical packages, findings, and decisions. Repeating a decision returns **409**. A successful match alone does not approve or park an invoice in SAP.

## Test missing documents and corrections

Change the test invoice number to `DEMO-INV-002` in both invoice and tax fields, then set `tax_invoices` to `[]` before posting a new case. Expect `status: "incomplete"` and a missing-document finding. AP approval returns **422**.

To supply the missing tax document, use `POST /v1/paper/cases/{case_id}/versions` and paste [case_revision.json](../examples/paper/case_revision.json). This wraps the entire corrected package with `expected_version: 1`, keeping `DEMO-INV-002` in both documents. Expect **201**, version `2`, and `status: "matched"`. Version `1` remains in history. The old version cannot receive a new AP decision once version `2` exists.

## Test mismatches and permitted exceptions

Use a new invoice number in both documents for each independent case. These scenarios use the default policy:

| Change to the sample package | Expected result |
| --- | --- |
| Change `invoice.fields.bank_account` to `009999` | `mismatched`, with `bank_mismatch` |
| Change `invoice.fields.total` without changing subtotal/tax | `mismatched`, with `amount_mismatch` |
| Change an extracted vendor/store/contract identifier while retaining the package identity | `mismatched`; AP override is forbidden |
| Remove a required field or tax document | `incomplete`; AP override is forbidden |
| Remove the agreement's supported billing basis before publishing a new reference | `needs_review`, with `pricing_basis_unconfigured` |
| Submit the same vendor/invoice number as an existing case | `duplicate`, with `duplicate_of`; AP approval is forbidden |

For the bank-only mismatch, an authorized reviewer may explicitly accept the configured exception:

```json
{
  "action": "approve",
  "reason": "Beneficiary verified independently for this synthetic case",
  "override_codes": ["bank_mismatch"]
}
```

Expect an approved decision retaining that code and reason. Every unresolved finding code must be both accepted and permitted by host policy. Supplying an unrelated override, omitting an unresolved code, or attempting to override structural blockers returns **422**. A rejection uses `{"action":"reject","reason":"Vendor correction required"}` and does not require a current agreement lookup.

Duplicate claims use exact canonical vendor ID plus extracted invoice number within the tenant. Claims survive corrections and rejection; revising the original case can reuse its own claim. Re-scanning, fuzzy OCR differences, and external AP ledger duplicates need additional host rules or integrations.

## Test a stale agreement reference

1. Create a new matched case and leave it undecided.
2. Append agreement version `2` using the agreement's revision endpoint and the same effective period. Approve version `2` with its own review reason.
3. Attempt to approve the old matched case version. Expect **409**, asking for a new assessment.
4. Append a new case version with its unchanged package. Its assessment should reference agreement version `2`; review and decide this new case version.

AP approval locks the case and referenced agreement, then verifies current agreement authority and the reconciliation policy. Changes to case content, approved reference versions, or policy fingerprints require reassessment. A newer unapproved agreement draft does not replace the approved reference.

## Queued PAPER extraction through Swagger

Use `POST /v1/paper/extractions` with multipart `file`, `schema_name` (`rent_agreement` or `rent_invoice`), and `content_mode` (`text` or `multimodal`, default `text`). Expect **202** with a saved `job_id`. Model inference runs in background workers after submission.

Poll `GET /v1/paper/extractions/{job_id}` for status and the persisted `result`. `GET /v1/paper/extractions?limit=10&offset=0` lists lightweight history metadata. `GET /v1/paper/extractions/{job_id}/file` serves the tenant-authorized original PDF. `POST /v1/paper/extractions/{job_id}/retry` accepts failed jobs only and returns **202** for a new attempt. Keep the old ID to inspect its earlier failure. These endpoints do not create approved agreements or invoice cases; the UI's explicit draft handoff and save actions do that separately.

### Clause fidelity, metering and recoverable cleanup

The deployment opts `paper.rent_agreement` into `source_text_strategy: verbatim`. For schema fields annotated `x-source-text`, a model selects host-issued paragraph IDs and the host copies the original text into the values and evidence. Complete context is supplied within explicit budgets; missing OCR, invalid selections or oversized clauses retain an unresolved candidate with a review warning. The default reusable service and unlisted schemas retain their existing behavior. Literal copying prevents paraphrased actors/triggers within selected paragraphs; it does not establish complete clause coverage, OCR accuracy or legal approval.

A source-reviewed draft can restore omitted context while retaining the automatic extraction separately. Its change reason records those interventions. If clause arrays are regrouped or generated allocations removed, old candidate diagnostics must retain their original code/path and extraction reference as explicit history events, with current narrative and party review markers kept separately. Open **Agreement master**, select the latest draft, and use **Review tools → Evidence** for the revised clauses and all their page shortcuts. Viewing evidence does not check the approval acknowledgements.

Open an extraction or a saved agreement's document review to see **Total reported tokens** and **Estimated cost**, with a collapsible call ledger and retained pricing basis. OCR, field generation, review, evidence repair and retries are metered through the same provider-neutral gateway. Historical attempts without metering show **Unavailable**. Unknown calls and missing prices produce explicit partial/unavailable coverage; known subtotals are not total charges. Failed response usage, when supplied by the provider, remains billable usage in the ledger. Actual provider invoices may differ from a configured public-price estimate. When verified OCR was reused, the UI explicitly excludes its earlier, unrecorded tokens and cost.

Prices are host-owned optional `profiles.<name>.pricing` configuration, never a model-name lookup baked into the library. Supply `pricing_id`, exact configured `model_id`, `currency`, decimal-string `input_per_million` and `output_per_million`, optional `cached_input_per_million`, `source`, and optional `as_of`. `allowed_response_model_ids` explicitly binds compatible reported snapshot IDs; other reported model identities keep token usage but no price. A cached price requires a reported cached-token count. Keep account credentials out of this snapshot and replace the rate reference when changing providers or models.

Choose **Archive attempt** to remove a completed/failed extraction from active upload lists. **Show archived attempts** opens the recovery list; select an attempt and choose **Restore attempt**. Archive/restore retains PDFs, extraction artifacts, usage, timestamps and saved agreement versions. Active jobs cannot be archived. Swagger exposes the same tenant-scoped operation through `POST /v1/paper/extractions/archive` with `{"job_ids":["saved-job-id"],"archived":true}` (or `false` to restore); `GET /v1/paper/extractions?archived=true` lists archived records. Direct source reads and document page shortcuts remain available for archived attempts.

### Compare the original with extracted fields

Select a saved upload on `/paper`. Desktop review shows the original PDF on the left and canonical values on the right. On narrow screens, switch **Original / Fields**; switching panes preserves unsaved edits. Use the page number, previous/next buttons, or zoom controls to inspect a clause. Evidence **Page** buttons open its exact original page when the cited block can be resolved unambiguously.

Choose **Review / edit agreement** (or invoice) to open the workflow editor. An existing unsaved draft requires an explicit replacement choice. The same original-page viewer remains available beside the editable draft. Changing the draft's source identity hides an unrelated PDF. Source navigation is UI state, separate from the canonical JSON submitted to an external system.

`GET /v1/paper/extractions/{job_id}/pages/{page_number}` serves a tenant-authorized original-page PNG. Page numbers are one-based and limited to 1–500; missing source/pages return 404. Rendering uses no OCR or model, runs off the event loop, and is bounded to 15 seconds, 100 MiB PDF input and 10 million image pixels. Preview responses are private and non-cacheable. **Open original PDF** remains available for full-resolution inspection.

### What happens after extraction?

1. **Review and correct the draft.** Verify the source, evidence, identities, dates, pricing basis and payment conditions. A literal quote establishes traceability; it does not prove the extracted field has the right business meaning.
2. **Save the agreement version.** Supply host-owned vendor/store identifiers and other required review information. Saving preserves a draft; it does not authorize it as a master.
3. **Approve the exact agreement version.** An authorized reviewer records classification, effective dates and a reason. This approved version becomes the reference for matching invoice periods.
4. **Build and reconcile the invoice package.** Review the extracted invoice, associate the agreement identity, and add required tax/supporting documents. Reconciliation reports missing documents, duplicates, identity, bank, amount and supported pricing checks.
5. **Review findings and record the AP decision.** Correct incomplete data or record only policy-permitted exceptions before approval/rejection. Unsupported pricing arrangements remain review findings. An AP decision does not post to SAP, send email or execute payment.

The supplied agreement has annual pricing and two advance rent installments, plus a separately conditional deposit. Optional installment and withholding rules now compare an invoice against an explicitly approved payment schedule and rounding policy. Annual source pricing stays unchanged. Unknown invoice service periods stay unknown; a separately recorded allocation requires review. Obtain external vendor/store IDs, bank details and actual withholding evidence, and confirm the proposed allocation and rounding policy before approving the real records.

### Test installments and withholding through the UI

Docker Compose enables the versioned rules through `configs/paper_reconciliation.yaml`. For a manually started backend, set `PAPER_RECONCILIATION_CONFIG_PATH=configs/paper_reconciliation.yaml`. The reusable library and packaged configuration leave these optional rules disabled. Undecided cases assessed under an older policy must be reassessed before approval.

1. Open `/paper`, create or review an agreement draft, and enter its source-supported installment schedule, payment conditions, pricing discrepancies, and reviewed withholding policy. Keep source prices unchanged. Obtain host identifiers and required review inputs before saving.
2. Choose **Save draft version**, then review and approve the exact agreement version with your accounting policy reference and reason. Saved installment identifiers remain stable across revisions; use a new agreement version to correct amounts, conditions or coverage.
3. Choose **Use for invoice**, then **New invoice package** if another case is selected. Supply the actual invoice source, invoice number, signed amounts, currency, and selected installment. Record an allocation separately only when the source service period is unknown and an authorized reviewer can establish it.
4. Choose **Add withholding certificate fields** and supply the actual source ID, reference number, date, invoice number, vendor/store/contract identifiers, currency, and withheld total. This is a blank attachment entry; no source evidence or amounts are invented. Positive VAT also requires the appropriate VAT invoice evidence.
5. Choose **Reconcile package** and inspect all findings. Conditional installments or source discrepancies can require explicit review. Missing certificates, unrelated references, incorrect deductions, and inconsistent net amounts prevent approval. Record only the permitted exception acknowledgements and a decision reason before approving.
6. Reopen the saved case to inspect its assessment and decision history. Using a different invoice number for the same saved installment returns **Duplicate**. Correcting an incomplete package creates a new case revision. Decisions retain the exact case, agreement and rule versions; approval does not execute payment or post to SAP.

The signed legacy `tax_amount` equals VAT minus withholding when using the structured payment fields and is not deducted again. The host's explicit policy permits a zero-VAT withholding package without a fabricated VAT invoice.

One invoice currently settles one complete scheduled installment. Partial installment splits, deposits, working-day deadline calculation and payment execution require separate capabilities. Conditional payment prerequisites remain explicit human-review findings. Reserved installment claims persist after rejection; cancellation or release needs a deliberate future workflow.

Development-only synthetic JSON fixtures remain at `examples/paper/installment_agreement.json` and `examples/paper/installment_invoice_package.json` for isolated manual/Swagger verification. Their fixed identities intentionally exercise duplicate protection on repeated submission. The web app has no demo generator or synthetic withholding-certificate loader.

The supplied PDF mapping is saved separately under ignored `data/runtime/paper-real-sample/agreement-installment-review-draft.json` and `invoice-installment-review-fields.json`. It remains an unapproved source-review candidate. Its whole-lease allocation, whole-Rupiah downward rounding and explicit zero-VAT review input require confirmation. No invoice service periods, host IDs, bank details or withholding certificate were invented; original PDFs and automatic extraction history remain preserved.

## Stateless extraction and external-system embedding

`POST /v1/extract` and `POST /v1/extract/fields` remain stateless HTTP request/response boundaries: they return extraction results directly and create **no ingestion job, upload history entry, or stored review draft**. They suit external systems that own artifact storage, unlike the queued PAPER upload endpoint above. The underlying async Python extraction service can also run without FastAPI, PostgreSQL, or the queue.

For each real PDF, execute `GET /v1/paper/schemas/{name}` for its role, such as `rent_agreement`, `rent_invoice`, or `tax_invoice`. Copy the full returned schema envelope into `POST /v1/extract`'s `schema_json` form field. Select the PDF and set `options_json` to `{"content_mode":"multimodal"}` or `{"content_mode":"text"}` as needed. Configure the existing extraction model profiles for the requested OCR, visual, and field features; packaged defaults supply native extraction without a field model.

When embedding or mapping stateless results yourself, copy `fields.data` into the corresponding agreement terms or package document's `fields`. Set its source identifier from `document.document_id`, retain `fields.evidence`, and carry document and field warnings, plus workflow warnings when present. Keep the original PDF and full document result in your host artifact storage. The queued PAPER path handles this storage and UI mapping for its two supported draft roles. Extraction output remains source evidence; agreement and AP review remain explicit decisions.

For an agreement, evidence needs the document-qualified shape `{"document_id":"...","evidence":{...}}`; package documents already qualify their evidence through `source_document_id`. Agreement warnings require explicit reviewer acknowledgement. Package warnings create review findings accepted through an allowed `extraction_warnings` AP override.

## Configuration and extension boundaries

Set server-owned `PAPER_RECONCILIATION_CONFIG_PATH` to a YAML policy override, or inject `app.state.paper_reconciliation_settings`. Policy controls required document roles/fields/supporting types, amount tolerance, explicit fixed-rent billing basis, allowed AP roles/exceptions, independent-review requirements, and deadlines. Optional `installments` and `withholding` rules use approved typed terms and exact decimal arithmetic. The approved rate and rounding policy are host review inputs, not a jurisdictional tax-law inference. Monthly pricing supports one full calendar month; revenue-share, mixed rent, and unsupported periods require review.

External applications can inject `BaseInvoiceCaseRepository`, an `AgreementMasterService` using their storage, and `ReconciliationEngine` into `InvoiceCaseService`. Case and agreement adapters must share the transaction for decision locking and reference reads. Inject versioned `BaseReconciliationRule` implementations for additional pure checks; their IDs and versions join the policy fingerprint. Additional rules retain the built-in blockers and pricing review requirements. Up to 100 documents, 64 extra rules, and 100 findings per extra rule fit the assessed package boundary.

This phase stores queued PDF extraction history, explicit agreement drafts and approvals, invoice cases, and AP decisions. Mailbox delivery/replies, automatic background rematching, SAP parking, and payments remain separate integrations.
## Contract association before reconciliation

1. Open **PAPER review → Document inbox**, review the invoice and **Save reviewed version**, then **Prepare case**.
2. Review **Contract association**. Suggestions scan approved agreements in batches. Matching references, different source values, missing identifiers and unknown coverage are visible. Search by supplier, property or contract number; use **Next batch** when more records remain. A candidate's ranking is advisory, not model confidence or proof of association.
3. Select a candidate. Use the page shortcuts in **Invoice source** and **Approved contract** to inspect both PDFs. The source reader supports multiple pages/documents, quotes, zoom and returning to the original field. Unresolved or unavailable citations remain explicit.
4. Complete invoice data and any reviewed installment allocation. The selected exact contract provides a schedule preview. Source/allocation edits invalidate an earlier confirmation; refresh suggestions and select the candidate again after completing edits.
5. Enter a reason and choose **Confirm contract association**. Master vendor/store/contract IDs are assigned separately; extracted document fields, evidence and warnings are retained. No confirmation is stored until **Run reconciliation** succeeds. The server records the authenticated reviewer, time, exact approved contract version, comparison signals and source/allocation fingerprint.
6. Reconcile the package, inspect the saved comparison and record the separate AP decision. Saved versions show association provenance. A changed approved version or edited invoice requires reconfirmation; another contract identity requires a new case. Historical API packages without an association remain supported and display as legacy assigned identities.

For the reviewed documents, the approved contract v6 has a reviewer-confirmed association, but invoice service coverage remains unknown. Selection alone does not establish a verified match or payment eligibility. Supply separately reviewed allocation and actual supporting documents before reassessing. No dummy agreements or invoice cases are created by these controls.

For embedding, use the validated `AssociationQuery` with `AssociationService.suggest()` or `POST /v1/paper/cases/association/candidates`. Submit only the selected `agreement_id`, `version_number` and reviewer `reason` under the package's `association`; `InvoiceCaseService` revalidates and stamps trusted provenance when saving. Inject `BaseAssociationMatcher` to extend candidate ranking without changing extraction, storage or reconciliation rules. Optional server-owned `PAPER_ASSOCIATION_CONFIG_PATH` overrides the bundled YAML policy; clients cannot choose ranking policy. Catalog search filters each bounded batch, so use batch navigation when a record is outside the current batch.

## Money display and input

PAPER formats known monetary fields in extracted values, source evidence comparisons, agreement terms, payment schedules, invoice amounts and reconciliation comparisons. These examples are synthetic. IDR uses dots for thousands and a comma for decimals: `1234567.89` appears as `IDR 1.234.567,89`, and `45000.00` as `IDR 45.000,00`. Other explicit currency codes use comma grouping and dot decimals, such as `USD 1,234,567.89`. Unknown currency uses neutral separators without inventing a currency code. Each schedule and document retains its own currency; no currency conversion occurs.

To test without saving, create a local agreement revision and replace **Schedule total gross rent** with the synthetic value `1.234.567,89`. Click elsewhere: the input stays grouped, while **Advanced payment rule JSON** shows the exact canonical string `1234567.89`. Ungrouped `1234567,89` is also accepted. For IDR, use a comma for decimals; malformed grouping such as `12.34.567,89` displays guidance and blocks form submission. Correct it before saving, or **Cancel** to discard the revision. Currency changes reformat the existing canonical amount rather than reinterpreting its separators.

Formatting preserves all fractional digits, negative signs, zeros and amounts beyond JavaScript's safe-integer range. Identifiers, bank accounts, quantities, fractional rates, literal quotations and advanced JSON remain exact. Raw JSON/API inputs continue to use canonical dot-decimal strings without grouping. Existing reconciliation arithmetic and approvals are unchanged.

## Source-reviewed workflow walkthrough verified on 2026-10-18

In **Contracts**, a locally approved agreement demonstrates the workflow using an explicitly labelled development policy reference. The approval reason records test provenance, source review and outstanding allocation/tax configuration. This is a development workflow demonstration; the policy reference is not an approved organization accounting policy. Assigned master IDs remain separate from unknown source IDs.

In **Cases**, the reviewed invoice records a confirmed association to that agreement. The saved result is **Incomplete**, with four blocking findings: tax invoice missing, service-period start missing, service-period end missing, and no approved authority established for the service period. Invoice/due dates were not substituted for service dates. No invoice approval or payment was made.

The comparison shows the selected approved contract as **reference only** until coverage is verified. Source buttons open either original PDF and retain field quotations; payment conditions have page 1/2/12 shortcuts and a **Read full source payment schedule** disclosure. **Contract pricing review** displays the retained printed-total discrepancy separately from the saved reconciliation findings. The original gross, signed deduction and net values remain unchanged. Currency was reviewed from invoice page 1; original extraction remains intact.

To proceed, an authorized reviewer must establish the approved installment allocation/coverage and withholding/rounding settings and provide actual supporting tax evidence. The two supplied PDFs alone do not establish the missing certificate. An older duplicate record with unverified allocation dates was excluded from this test.

In agreement **Review tools → Review issues**, **Needs review** groups current issues by field. **Missing values** shows absent/empty fields; **Verify values** shows extracted fields still requiring checks. Each row gives a brief reason, next action, source-page shortcuts and collapsed exact Details. **Extraction history** retains earlier diagnostics; successful values live in **All fields**. **Evidence** contains field quotations; **Sources** lists original documents. Viewing entries does not resolve or acknowledge them automatically.

The existing invoice extraction was restored from Archived attempts without another model call. The verification summary and UI screenshots remain in ignored local runtime artifacts.

## Workspace indexes and legacy source links

The additive read-only endpoints `GET /v1/paper/workspace/cases`, `/contracts` and `/documents` provide tenant-scoped, bounded search/filter/pagination. Confirmed contract relationships come from saved associations, never inferred names or amounts. Source links retain exact historical versions; unavailable source identity is shown as **Saved links unavailable**, rather than claiming there is no saved workflow. These indexes and UI navigation use existing workflow services and make no model calls. No migration is required.

For older completed uploads missing `meta.document_id`, run `python scripts/backfill_paper_document_ids.py --tenant-id TENANT --job-id JOB --dry-run` in the configured application environment. Inspect the report, then use the same exact arguments with `--apply` to add a validated source ID. The repair reads only job-owned, tenant-validated artifacts; it preserves source files, extraction results, archive state, processing timestamps, saved versions and decisions. The default is dry-run; a bounded batch accepts `--limit` from 1 to 100. Use exact job IDs when repairing records outside that batch.

The case-oriented UI verification repaired six missing legacy source IDs. Agreement and case history fingerprints are unchanged; no extraction or financial decision was made. Report: `data/runtime/paper-real-sample/case-workspace-verification.json`. Screenshot: `case-oriented-workspace.jpg` in the same directory.
