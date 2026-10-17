# Test PAPER agreements and invoice cases

Open [PAPER review](http://localhost:5173/paper) to upload PDFs, review extraction results, and prepare editable agreement or invoice drafts. Manual forms and JSON imports remain available. [Swagger UI](http://localhost:8010/docs) exposes the same queued extraction, approved agreement master, reconciliation service, and persisted review decisions. The web app starts manual drafts with empty document fields and has no synthetic example loaders or approval autofill controls.

## Navigate the guided workspace

The three stages are **Documents**, **Agreement master**, and **Invoices**. **Review / edit agreement** opens its local editor in **Agreement master → Rent Agreement Master Repository**; **Review / edit invoice** opens Invoices. With an unsaved editor already open, a replace/keep choice protects that work. **Use for invoice** opens Invoices. Switching stages preserves unsaved form edits while this page stays open; reloading or leaving the page still requires saving first. The stage tabs also support arrow keys, Home, and End.

**Documents** keeps upload, recent results, warning counts, and the next draft action visible. Extraction options sit beside the upload controls on wider screens, and recent uploads use responsive card columns. Open **Extraction options** to change text/multimodal mode and **Extraction details and downloads** for IDs, full text, and result downloads. Desktop review shows original and extracted content together; compact layouts provide **Original / Extracted** controls.

Original and extracted page controls share one page selection. **This page** shows the selected page's stored text, tables and exactly linked canonical values; next/previous actions on either side update both sides and reset their scroll positions. Missing extraction or absent page citations are stated explicitly, with no content borrowed from another page. **All fields** shows the complete saved extraction and citations. Editable drafts open in **Edit all fields**; changing a source page opens page review, and returning to the editor preserves unsaved inputs and unapplied JSON. Page-specific draft values retain earlier evidence, so source verification is still required after edits. Short values use multiple columns when space permits; long prose and structured values retain full-width space.

**Review tools** stays at the bottom right while scrolling a document or draft. **Evidence**, **Warnings**, and **Sources** open a non-modal inspector with its own scroll area, so the long form no longer has an evidence footer to scroll to. Search evidence by field path or quoted text; search warnings by code, message or field. With an original attached, **Current PDF page only** filters citations to exact page links and warnings to that page plus unscoped warnings. Clear the filter to see unresolved citations too. **Sources** retains document references and explicitly states when no original preview is attached. Close the inspector with its close button or Escape; focus returns to its toolbar.

Each extracted field and ordinary schema editor field has **Evidence** and source shortcuts. **Evidence** opens only that field's exact and descendant citations without moving you away from the field. A single-page **source icon / p. N** opens the original and its evidence together. **N pages** expands every linked page button, including citations attached to nested values. Citation cards also expose all their linked pages. **Back to field** closes the inspector, reveals **All fields / Edit all fields**, and restores the field and scroll position. Shortcuts preserve unsaved controls and unapplied JSON; on compact screens they reveal **Original** when opening a page. **No linked source** opens evidence details without guessing a page. Evidence from other documents and ambiguous source IDs remain unlinked. Edited values retain earlier citations and still require source verification.

The **Rent Agreement Master Repository** contains saved drafts and approved versions. A local editor is labelled **Unsaved draft · local changes**; it is not yet a saved record. **Save draft version**, at the editor's top and bottom, validates required identity/effective-date/source/reason inputs and saves a version. The saved version then exposes its separate approval form and version history. Only an approved version can be used as the authoritative invoice reference.

Agreement terms are grouped into sections. **Field guidance**, source references, and exact JSON expand on demand. Invalid controls inside a collapsed section reopen that section and receive focus. Warnings, source discrepancies, installment conditions, and explicit AP acknowledgements remain available; nothing is automatically acknowledged. **How it works** explains the flow, and **Workspace** shows reviewer access and the active policy.

Use **New draft** for an agreement and **New invoice package** for an invoice. Enter source-verified values or import your own typed JSON; agreement classification, policy references, and approval reasons require reviewer input. **Add withholding certificate fields** creates a blank document entry. Subtle stage/disclosure transitions and loading indicators respect the operating system's reduced-motion preference.

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
