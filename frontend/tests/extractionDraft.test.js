import test from 'node:test'
import assert from 'node:assert/strict'
import { agreementFromExtraction, invoiceFromExtraction, extractionWarnings, canPrepareDraft } from '../src/paper/extractionDraft.js'

const fixture = (schema = 'rent_agreement') => ({
  job_id: 'job-1', schema_name: schema, status: 'completed',
  result: {
    document: { document_id: 'hash-1', text: 'Source text', warnings: [{ code: 'ocr_uncertain', message: 'Check scan', page_number: 1 }] },
    fields: { schema_id: `paper.${schema}`, schema_version: '1', data: { vendor_name: 'Landlord', vendor_id: null, lease_start_date: '2027-01-05', lease_end_date: '2032-01-04', fixed_rent: '327777777', extensions: { fixed_rent_basis: 'annual' } }, evidence: [{ field_path: '/fixed_rent', source_ids: ['p9-page-text'], quote: '327.777.777' }], warnings: [{ code: 'missing_field', message: 'Not in source', field_path: '/vendor_id' }] },
    warnings: [{ code: 'review_required', message: 'Review fields' }],
  },
})

test('agreement mapping retains exact source evidence and all warnings without fabricating host identity', () => {
  const source = fixture()
  const mapped = agreementFromExtraction(source)
  assert.deepEqual(mapped.identity, { vendor_id: '', store_id: '', contract_number: '' })
  assert.equal(mapped.draft.terms.vendor_id, null)
  assert.equal(mapped.draft.effective_from, '2027-01-05')
  assert.equal(mapped.draft.effective_to, '2032-01-04')
  assert.deepEqual(mapped.draft.source_document_ids, ['hash-1'])
  assert.deepEqual(mapped.draft.evidence, [{ document_id: 'hash-1', evidence: source.result.fields.evidence[0] }])
  assert.equal(mapped.draft.extraction_warnings.length, 3)
  mapped.draft.terms.extensions.fixed_rent_basis = 'monthly'
  mapped.draft.evidence[0].evidence.quote = 'Edited'
  assert.equal(source.result.fields.data.extensions.fixed_rent_basis, 'annual')
  assert.equal(source.result.fields.evidence[0].quote, '327.777.777')
})

test('invoice mapping preserves absent service dates and source metadata, with empty optional documents', () => {
  const source = fixture('rent_invoice')
  source.result.fields.data = { vendor_name: 'Landlord', vendor_id: null, total: '885000000.00', service_period_start: null }
  const mapped = invoiceFromExtraction(source)
  assert.deepEqual(mapped.identity, { vendor_id: '', store_id: '', contract_number: '' })
  assert.equal(mapped.invoice.source_document_id, 'hash-1')
  assert.equal(mapped.invoice.fields.service_period_start, null)
  assert.equal(mapped.invoice.fields.service_period_end, undefined)
  assert.equal(mapped.invoice.fields.total, '885000000.00')
  assert.equal(mapped.invoice.warnings.length, 3)
  assert.deepEqual(mapped.tax_invoices, [])
  assert.deepEqual(mapped.utility_statements, [])
  assert.deepEqual(mapped.supporting_documents, [])
  mapped.invoice.evidence[0].quote = 'Edited'
  assert.equal(source.result.fields.evidence[0].quote, '327.777.777')
})

test('partial text-only results create an empty review draft retaining source and warnings without fabricating fields', () => {
  const source = fixture()
  source.result.fields = null
  assert.equal(canPrepareDraft(source), false)
  const draft = agreementFromExtraction(source)
  assert.deepEqual(draft.draft.terms, {})
  assert.deepEqual(draft.draft.source_document_ids, ['hash-1'])
  assert.equal(draft.draft.extraction_warnings.length, 2)
  assert.deepEqual(draft.draft.evidence, [])
  assert.equal(draft.draft.effective_from, '')
  assert.equal(extractionWarnings(source).length, 2)
  source.result.fields = { schema_id: 'paper.rent_invoice', data: {} }
  assert.equal(canPrepareDraft(source), false)
  assert.throws(() => agreementFromExtraction(source), /canonical fields/i)
  source.status = 'processing'
  assert.equal(canPrepareDraft(source), false)
})

test('warning projection deduplicates shared document and result issues without dropping page or field context', () => {
  const source = fixture()
  source.result.warnings.push(source.result.document.warnings[0])
  assert.equal(extractionWarnings(source).length, 3)
  assert.equal(extractionWarnings(source)[0].page_number, 1)
})
