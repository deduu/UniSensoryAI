import test from 'node:test'
import assert from 'node:assert/strict'
import { addReviewedDraft, draftReference, hydrateDraftSelection, packageFromDraftSelection, removeSelectedDraft } from '../src/paper/draftSelection.js'

const invoice = { draft_id: 'invoice', version_number: 2, role: 'rent_invoice', status: 'reviewed', document: { source_document_id: 'pdf-1', fields: { total: '12345678901234567890.01' }, evidence: [{ page: 1 }], warnings: ['retained'], extension: { untouched: true } } }
const tax = { draft_id: 'tax', version_number: 3, role: 'tax_invoice', status: 'reviewed', document: { source_document_id: 'pdf-2', fields: { tax_number: '007' }, evidence: [{ page: 2 }] } }
const selection = { invoice: draftReference(invoice), tax_invoices: [], utility_statements: [], supporting_documents: [] }

test('adding a reviewed exact version preserves the original selection', () => {
  const added = addReviewedDraft(selection, tax, [invoice])
  assert.deepEqual(added.tax_invoices, [{ draft_id: 'tax', version_number: 3 }])
  assert.deepEqual(selection.tax_invoices, [])
  assert.throws(() => addReviewedDraft(added, tax, [invoice, tax]), /already selected/)
  assert.deepEqual(removeSelectedDraft(added, 'tax_invoice', draftReference(tax)), selection)
})

test('only reviewed documents with unique canonical sources may be selected', () => {
  assert.throws(() => addReviewedDraft(selection, { ...tax, status: 'draft' }, [invoice]), /reviewed/)
  assert.throws(() => addReviewedDraft(selection, { ...tax, document: { source_document_id: 'pdf-1' } }, [invoice]), /source document/)
  assert.throws(() => addReviewedDraft(selection, { ...tax, document: { fields: {} } }, [invoice]), /source document/)
  assert.throws(() => draftReference({ ...tax, version_number: 0 }), /version/)
})

test('selection package preserves exact decimal strings, citations, unknown attributes and package metadata', () => {
  const selected = addReviewedDraft(selection, tax, [invoice])
  const original = { identity: { vendor_id: 'assigned' }, association: { agreement_id: 'contract', version_number: 6 }, extension: { retained: true }, invoice: { stale: true } }
  const pkg = packageFromDraftSelection(original, selected, [invoice, tax])
  assert.deepEqual(pkg.invoice, invoice.document)
  assert.deepEqual(pkg.tax_invoices, [tax.document])
  assert.equal(pkg.invoice.fields.total, '12345678901234567890.01')
  assert.deepEqual(pkg.association, original.association)
  assert.equal(original.invoice.stale, true)
  pkg.invoice.evidence[0].page = 99
  assert.equal(invoice.document.evidence[0].page, 1)
})

test('exact-version hydration rejects an API silently returning another version or role', async () => {
  const calls = []
  const api = { documentDraftVersion: async (id, version) => { calls.push([id, version]); return { ...invoice, version_number: 3 } } }
  await assert.rejects(hydrateDraftSelection(api, selection), /requested version/)
  assert.deepEqual(calls, [['invoice', 2]])
  await assert.rejects(hydrateDraftSelection({ documentDraftVersion: async () => ({ ...invoice, role: 'tax_invoice' }) }, selection), /role/)
})

test('hydration verifies every selected source and enforces a bounded package', async () => {
  const selected = addReviewedDraft(selection, tax, [invoice])
  const api = { documentDraftVersion: async id => id === 'invoice' ? invoice : tax }
  assert.deepEqual(await hydrateDraftSelection(api, selected), [invoice, tax])
  const tooMany = { ...selection, supporting_documents: Array.from({ length: 101 }, (_, n) => ({ draft_id: `s-${n}`, version_number: 1 })) }
  await assert.rejects(hydrateDraftSelection(api, tooMany), /100/)
})

test('a case cannot select multiple versions of one draft or exceed 100 documents total', async () => {
  const duplicate = { ...selection, tax_invoices: [{ draft_id: 'invoice', version_number: 3 }] }
  await assert.rejects(hydrateDraftSelection({}, duplicate), /one version/)
  const tooMany = { ...selection, supporting_documents: Array.from({ length: 100 }, (_, n) => ({ draft_id: `s-${n}`, version_number: 1 })) }
  await assert.rejects(hydrateDraftSelection({}, tooMany), /100/)
})
