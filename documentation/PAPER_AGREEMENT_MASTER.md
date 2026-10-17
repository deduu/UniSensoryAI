# PAPER schemas and approved agreement master

Phase one provides five external document schemas and an async agreement master with tenant scope, immutable content versions, explicit approval records, and effective-date lookup. PAPER consumes the existing extraction service; it does not construct or select inference models. Existing document pipelines, chat, policy review, and extraction endpoints retain their behavior.

The next manual reconciliation phase adds durable invoice cases, completeness/matching findings, duplicate claims, and audited AP decisions. Follow [PAPER UI testing](PAPER_UI_TESTING.md) for executable Swagger scenarios and external embedding boundaries.

## External extraction schemas

Import schema models or `get_paper_schema` from `src.paper.schemas`. The portable catalog uses JSON Schema 2020-12, local references, stable `paper.*` identities, and version `1`.

| Catalog name | Schema class | Principal information |
| --- | --- | --- |
| `rent_agreement` | `RentAgreementSchema` | Vendor/store/contract, lease dates and duration, payment schedule, fixed/revenue-share/mixed rent, currency, minimum guarantee, renewal and other terms, bank account |
| `rent_invoice` | `RentInvoiceSchema` | Vendor/store/contract, invoice and service dates, amounts/tax, currency, bank details, line items |
| `tax_invoice` | `TaxInvoiceSchema` | Tax document and related invoice, supplier/customer tax identity, date, taxable amount/tax, vendor/store and service period |
| `utility_statement` | `UtilityStatementSchema` | Vendor/store/contract/invoice, service period, utility/meter/usage, charges/tax, currency, bank details |
| `supporting_document` | `SupportingDocumentSchema` | Document role/reference, vendor/store/contract/invoice relationships, dates/amounts, and source-described terms |

Unknown extracted terms remain `null`. Monetary values and rates are plain decimal **strings**, preserving precision; `revenue_share_rate` is a fraction such as `"0.05"`. Account identifiers remain strings, including leading zeros. The schemas reject unrecognized top-level fields and permit explicit host attributes in `extensions`. For a different extraction contract, subclass a schema or pass the consuming application's own Pydantic/JSON Schema to `ExtractionService`; changing an external schema does not require a provider change.

These are extraction contracts, not approved accounting decisions. Classification lives in the agreement approval record. Portable JSON Schema checks individual dates and field shapes; PAPER typed models also check cross-field date ordering. The master revalidates typed terms before persistence. This phase stores agreement terms under `paper.rent_agreement@1`; the subsequent reconciliation module consumes the invoice schemas in durable case packages.

## Agreement version and approval semantics

`AgreementIdentity` contains the canonical vendor ID, store ID, and contract number supplied by the host. Its identity is unique within a tenant and remains stable across revisions. Supplied extracted identifiers must agree with that identity; a model does not resolve authoritative business identity.

`AgreementDraft` retains terms, schema identity/version, effective dates, source document IDs, document-qualified field evidence, extraction warnings, and a change reason. Each revision appends a new snapshot. `ApprovalRecord` separately retains classification (`psak73` or `non_psak73`), accounting rule ID/version, reviewer reason, warning acknowledgement, approved-by identity, and UTC approval time.

Approval requires host-established authority, the latest version, and the configured required terms. Defaults require vendor name, store, contract number, lease dates, payment schedule, rent type, and currency. Fixed rent requires its amount; revenue sharing requires its rate; mixed rent requires both. Missing required terms can be saved as drafts but cannot be approved. Existing extraction warnings require `acknowledge_extraction_warnings: true` and a review reason. Classification and rule references are explicit reviewer inputs; this phase neither evaluates PSAK rules nor stores or verifies the referenced rule definitions.

For approved lookup, use exact vendor/store/contract identity and an `as_of` business date. Only approvals in the current tenant participate. The highest approved version that has started by that date supersedes earlier versions; its effective end is inclusive. If that selected version has ended, lookup returns no match rather than revive an older approval. Future approved versions do not hide earlier applicable terms, and unapproved revisions do not hide approved reference data.

Version history is returned newest first and supports pagination. Repeated approval and stale revisions return conflicts. Correcting approved content requires a new version and another approval. The application offers no overwrite/delete operation for snapshots or approvals; ORM guards also reject changes to snapshots, approvals, or stable header identity. Database administrators and direct bulk SQL remain outside that application guarantee.

The master stores source references and evidence, rather than original PDFs or full extracted document results. The consuming host must retain those artifacts and enforce their access policy. Provenance validation checks source membership and contract shape; it does not independently prove source availability, quote correctness, or model accuracy.

## Embedding in an external application

`AgreementMasterService` depends only on `BaseAgreementRepository`, validated contracts, and settings. The supplied `SqlAlchemyAgreementRepository` uses an injected async session. An external application may implement the port for its own storage and supply trusted actors; no FastAPI, SQLAlchemy, or provider construction occurs inside the business service.

```python
from datetime import date

from src.extraction.contracts import ExtractionOptions, PdfSource
from src.extraction.service import ExtractionService
from src.paper.contracts import (
    AgreementActor, AgreementDraft, AgreementEvidence,
    AgreementIdentity, AgreementVersion,
)
from src.paper.schemas import RentAgreementSchema, get_paper_schema
from src.paper.service import AgreementMasterService


async def register_agreement(
    *,
    extraction: ExtractionService,
    master: AgreementMasterService,
    actor: AgreementActor,
    source: PdfSource,
    identity: AgreementIdentity,
    effective_from: date,
    effective_to: date,
) -> AgreementVersion:
    result = await extraction.extract(
        source,
        options=ExtractionOptions(content_mode="multimodal"),
        schema=get_paper_schema("rent_agreement"),
    )
    fields = result.fields
    if fields is None:
        raise ValueError("Agreement field extraction is required.")
    draft = AgreementDraft(
        terms=RentAgreementSchema.model_validate(fields.data),
        effective_from=effective_from,
        effective_to=effective_to,
        source_document_ids=(result.document.document_id,),
        evidence=tuple(
            AgreementEvidence(document_id=result.document.document_id, evidence=item)
            for item in fields.evidence
        ),
        extraction_warnings=result.document.warnings + fields.warnings,
        change_reason="Initial source extraction",
    )
    return await master.create_draft(actor=actor, identity=identity, draft=draft)
```

The host supplies configured `vision`/`fields` profiles through the existing extraction composition. It can request text output instead of multimodal content. Retain the returned document and warnings in host artifact storage, then present the draft for review. Approval is a separate `master.approve(...)` call with an `ApprovalDecision`; extraction does not auto-approve it. Custom agreement extraction attributes destined for this master's version-1 terms belong in `terms.extensions`.

The SQL adapter flushes changes within savepoints and never commits internally. The embedding host commits or rolls back its session. Version changes and approvals acquire the same database header lock through an atomic expected-version update, with uniqueness constraints preventing duplicate identities and approvals. After an uncertain transaction outcome, read the stored version/approval before retrying.

## HTTP integration

The existing server mounts the additive `/v1/paper` router. Authentication supplies tenant and user identity; request bodies cannot override either. Approval roles are read from the persisted user in that tenant, not from client JSON or a role claim. New OAuth users remain `member` until a trusted administrator grants an allowed role. A synthetic development identity without a persisted allowed role cannot approve.

| Method and route | Result |
| --- | --- |
| `GET /v1/paper/schemas` | All five version-1 portable schemas |
| `GET /v1/paper/schemas/{name}?version=1` | ExternalSchema envelope accepted by existing extraction APIs |
| `POST /v1/paper/agreements` | Create draft version 1, return 201 |
| `POST /v1/paper/agreements/{id}/versions` | Append `{expected_version, draft}`, return 201 |
| `GET /v1/paper/agreements/{id}/versions?limit=100&offset=0` | Version history, newest first |
| `GET /v1/paper/agreements/{id}/versions/{version}` | Exact draft or approved version |
| `POST /v1/paper/agreements/{id}/versions/{version}/approval` | Publish the reviewed latest version |
| `GET /v1/paper/agreements/approved?vendor_id=...&store_id=...&contract_number=...&as_of=2026-06-01` | Approved reference or 404 |

A synthetic initial request:

```json
{
  "identity": {"vendor_id": "vendor-1", "store_id": "store-1", "contract_number": "RA-1"},
  "draft": {
    "terms": {
      "vendor_name": "Example landlord", "vendor_id": "vendor-1",
      "store_id": "store-1", "contract_number": "RA-1",
      "lease_start_date": "2026-01-01", "lease_end_date": "2026-12-31",
      "payment_schedule": "Monthly", "rent_type": "fixed",
      "currency": "IDR", "fixed_rent": "1000000.00"
    },
    "effective_from": "2026-01-01", "effective_to": "2026-12-31",
    "source_document_ids": ["host-retained-extraction-document-id"],
    "change_reason": "Initial source extraction"
  }
}
```

An authorized reviewer separately submits `{"classification":"psak73","rule_set_id":"accounting-policy","rule_set_version":"2026.1","reason":"Reviewed against the approved policy"}` to the approval route. This synthetic value illustrates the transport, rather than a classification outcome for any real agreement. Include `acknowledge_extraction_warnings: true` when accepting retained extraction warnings.

Routes enforce 100 requests/second per caller with the existing in-process limiter. Storage calls have a configurable deadline capped at 15 seconds. Invalid inputs return 422, missing scoped records return 404, missing approval authority returns 403, version/identity/replay conflicts return 409, and storage deadlines return 504. Mutating endpoints commit before returning successful responses.

## Deployment and next phase

Apply the additive Alembic revision `8b3e1c725f60` after the existing tenant migration, using `alembic upgrade head` in the intended database environment. That revision creates only `paperagreements`, `paperagreementversions`, and `paperagreementapprovals`; it does not backfill or migrate existing document results. The subsequent `dc728f04a912` revision adds four invoice-case tables and is the current migration head. No live database is changed by adding migration files.

Packaged `src/paper/defaults.yaml` defines required fields, rent-specific requirements, allowed approval roles, independent-review policy, and storage timeout. Set the server-owned `PAPER_CONFIG_PATH` to a deployment YAML override or inject `app.state.paper_settings`. Configuration is validated and cached per application. Library hosts can inject `AgreementMasterSettings` directly. Enable the existing production authentication configuration as usual.

Manual invoice cases now consume these approved versions for package completeness, deterministic matching, duplicate handling, and AP decisions. Agreement summary generation, an accounting classification engine/rule repository, dashboard screens, email/SAP connectors, and background event processing remain separate work.

Phase-one verification on 2026-10-14: 90 new PAPER tests and 204 existing workflow regression tests passed. Strict typing, lint, formatting, offline PostgreSQL migration generation, and an isolated wheel embedding smoke test passed. Database integration tests use SQLite; no live PostgreSQL migration, concurrent PostgreSQL stress test, model inference accuracy, or accounting-rule validation is claimed.

Relevant implementation: [schemas](../src/paper/schemas/catalog.py), [master service](../src/paper/service.py), [repository port](../src/paper/ports/repository.py), [SQL adapter](../src/services/agreement_repository.py), [HTTP routes](../src/api/paper_routes.py), and [migration](../alembic/versions/8b3e1c725f60_add_paper_agreement_master.py).
