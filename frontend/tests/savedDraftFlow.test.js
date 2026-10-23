import test from 'node:test'
import assert from 'node:assert/strict'
import { draftSaveRequest, preparationRequest, readinessForPolicy } from '../src/paper/savedDraftFlow.js'

test('matching readiness cannot survive a settings revision or policy switch', () => {
  const context = { policy_id: 'paper.policy', policy_version: 'revision-4' }
  const ready = { ready: true, ...context, checks: [] }
  assert.equal(readinessForPolicy(ready, context), ready)
  assert.equal(readinessForPolicy(ready, { ...context, policy_version: 'revision-5' }), null)
  assert.equal(readinessForPolicy(ready, { ...context, policy_id: 'other' }), null)
  assert.equal(readinessForPolicy(ready, null), null)
  assert.equal(readinessForPolicy({ ready: true }, context), null)
  assert.equal(readinessForPolicy(null, context), null)
})

const selection = { invoice: { draft_id: 'invoice', version_number: 2 }, tax_invoices: [{ draft_id: 'tax', version_number: 1 }], utility_statements: [], supporting_documents: [], server_trusted: 'no' }
const pkg = { identity: { vendor_id: 'vendor', store_id: 'store', contract_number: '65', source: 'untrusted' }, invoice: { source_document_id: 'pdf-1', fields: { service_period_start: null, total: '1234567890.00' } }, association: { agreement_id: 'contract', version_number: 6, reason: 'Checked parties and location.', confirmed_by: 'forged', confirmed_at: 'forged', tenant_id: 'other' }, server_assessment: 'untrusted', document_versions: [{ reviewed_by: 'forged' }] }

test('preparation emits only selected references, assigned identity and association request intent', () => {
  const before = JSON.stringify(pkg)
  const request = preparationRequest({ selection, package: pkg })
  assert.deepEqual(request, { identity: { vendor_id: 'vendor', store_id: 'store', contract_number: '65' }, invoice: { draft_id: 'invoice', version_number: 2 }, tax_invoices: [{ draft_id: 'tax', version_number: 1 }], utility_statements: [], supporting_documents: [], association: { agreement_id: 'contract', version_number: 6, reason: 'Checked parties and location.' } })
  assert.equal(JSON.stringify(pkg), before)
  request.tax_invoices[0].version_number = 9
  assert.equal(selection.tax_invoices[0].version_number, 1)
  assert.doesNotMatch(JSON.stringify(request), /forged|source_document_id|server_assessment|service_period/)
})

test('preparation requires explicit association, assigned identity and paired revision guards', () => {
  assert.throws(() => preparationRequest({ selection, package: { ...pkg, association: null } }), /contract/)
  assert.throws(() => preparationRequest({ selection, package: { ...pkg, identity: { ...pkg.identity, vendor_id: ' ' } } }), /Vendor ID/)
  assert.throws(() => preparationRequest({ selection, package: pkg, caseId: 'case' }), /expected version/)
  const request = preparationRequest({ selection, package: pkg, caseId: 'case', expectedVersion: 3 })
  assert.equal(request.case_id, 'case')
  assert.equal(request.expected_version, 3)
})

test('reviewed allocation stays separate from extracted invoice fields and strips authority provenance', () => {
  const request = preparationRequest({ selection, package: { ...pkg, review_context: { allocation_start: '2027-01-05', allocation_end: '2029-01-04', reason: 'Verified advance installment allocation.', source_document_ids: ['pdf-1', 'contract-pdf'], approved_by: 'forged' } } })
  assert.deepEqual(request.review_context, { allocation_start: '2027-01-05', allocation_end: '2029-01-04', reason: 'Verified advance installment allocation.', source_document_ids: ['pdf-1', 'contract-pdf'] })
  assert.equal(pkg.invoice.fields.service_period_start, null)
  assert.throws(() => preparationRequest({ selection, package: { ...pkg, review_context: { allocation_start: '2028-01-01', allocation_end: '2027-01-01', reason: 'Wrong dates', source_document_ids: ['pdf'] } } }), /end/)
})

test('saving a source review contains no reconciliation or client reviewer provenance', () => {
  const document = { source_document_id: 'pdf-1', fields: { total: '12345678901234567890.01' }, evidence: [{ page: 1 }], warnings: ['retained'] }
  const saved = { draft_id: 'i', version_number: 4, role: 'rent_invoice', reviewed_by: 'old', association: pkg.association }
  const request = draftSaveRequest(saved, 'rent_invoice', document, true, 'Verified against original PDF.')
  assert.deepEqual(request, { expected_version: 4, role: 'rent_invoice', document, reviewed: true, reason: 'Verified against original PDF.' })
  assert.doesNotMatch(JSON.stringify(request), /association|reviewed_by|draft_id|assessment/)
  request.document.evidence[0].page = 8
  assert.equal(document.evidence[0].page, 1)
  assert.equal(draftSaveRequest(null, 'tax_invoice', document, false, 'Save pending review.').reviewed, false)
})

test('draft save rejects ambiguous role, malformed provenance guard and non-explicit review intent', () => {
  const document = pkg.invoice
  assert.throws(() => draftSaveRequest({ version_number: 2, role: 'tax_invoice' }, 'rent_invoice', document, true, 'Review'), /role/)
  assert.throws(() => draftSaveRequest(null, 'rent_invoice', document, 'true', 'Review'), /boolean/)
  assert.throws(() => draftSaveRequest({ version_number: 0, role: 'rent_invoice' }, 'rent_invoice', document, true, 'Review'), /version/)
  assert.throws(() => draftSaveRequest(null, 'rent_invoice', document, true, ' '), /reason/)
})
