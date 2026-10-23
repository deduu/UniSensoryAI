import test from 'node:test'
import assert from 'node:assert/strict'
import { associationFingerprint, invalidateAssociation, candidateAllowed, confirmAssociation, candidateAuthority, loadAssociationResources, associationSignalPaths, associationSignalResult } from '../src/paper/contractAssociation.js'

const identity = { vendor_id: 'vendor', store_id: 'site', contract_number: '65' }
const candidate = { agreement_id: 'agreement', version_number: 2, identity, eligible: true, coverage: 'verified' }
const pkg = { identity: { vendor_id: '', store_id: '', contract_number: '' }, invoice: { source_document_id: 'invoice-pdf', fields: { vendor_name: 'Source supplier', contract_number: null }, evidence: [{ field_path: '/vendor_name', source_ids: ['block'], quote: 'Source supplier' }], warnings: [{ code: 'missing' }] }, review_context: null, tax_invoices: [{ fields: { vendor_id: 'source-vendor' }, evidence: [] }], supporting_documents: [] }

test('review confirmation assigns identity separately and preserves original values and evidence', () => {
  const before = structuredClone(pkg)
  const result = confirmAssociation(pkg, candidate, '  Supplier and site checked in the PDFs.  ')
  assert.deepEqual(result.identity, identity)
  assert.deepEqual(result.association, { agreement_id: 'agreement', version_number: 2, reason: 'Supplier and site checked in the PDFs.' })
  assert.equal(result.invoice, pkg.invoice)
  assert.equal(result.tax_invoices, pkg.tax_invoices)
  assert.deepEqual(pkg, before)
  assert.equal(result.invoice.fields.contract_number, null)
})

test('confirmation requires a reason and an eligible exact candidate, including locked case identity', () => {
  assert.throws(() => confirmAssociation(pkg, candidate, ' '), /reason/i)
  for (const changes of [{ eligible: false }, { coverage: 'conflicting' }, { version_number: 0 }, { identity: { ...identity, vendor_id: '' } }]) {
    assert.equal(candidateAllowed({ ...candidate, ...changes }), false)
    assert.throws(() => confirmAssociation(pkg, { ...candidate, ...changes }, 'Reviewed'), /candidate/i)
  }
  assert.equal(candidateAllowed(candidate, { ...identity, store_id: 'different' }), false)
  assert.throws(() => confirmAssociation(pkg, candidate, 'Reviewed', { ...identity, store_id: 'different' }), /candidate/i)
  assert.equal(candidateAllowed({ ...candidate, coverage: 'unverified' }, identity), true)
})

test('invoice changes, reviewed allocation changes and assigned identity changes invalidate confirmation', () => {
  const confirmed = confirmAssociation(pkg, candidate, 'Reviewed source documents')
  const unrelated = { ...confirmed, supporting_documents: [{ source_document_id: 'attachment' }] }
  assert.equal(invalidateAssociation(confirmed, unrelated).association, confirmed.association)
  for (const changed of [
    { ...confirmed, invoice: { ...confirmed.invoice, fields: { ...confirmed.invoice.fields, vendor_name: 'Other supplier' } } },
    { ...confirmed, invoice: { ...confirmed.invoice, evidence: [] } },
    { ...confirmed, review_context: { allocation_start: '2027-01-01' } },
    { ...confirmed, identity: { ...identity, store_id: 'changed' } },
  ]) assert.equal(invalidateAssociation(confirmed, changed).association, null)
  assert.deepEqual(confirmed.invoice, pkg.invoice)
})

test('fingerprints are independent of property order and include evidence and billing context', () => {
  const reordered = { ...pkg, invoice: { warnings: pkg.invoice.warnings, evidence: pkg.invoice.evidence, fields: { contract_number: null, vendor_name: 'Source supplier' }, source_document_id: 'invoice-pdf' } }
  assert.equal(associationFingerprint(pkg), associationFingerprint(reordered))
  assert.notEqual(associationFingerprint(pkg), associationFingerprint({ ...pkg, review_context: { reason: 'allocation' } }))
})

const agreement = { agreement_id: 'agreement', version_number: 2, identity, approval: { approved_by: 'reviewer' }, draft: { source_document_ids: ['contract-pdf', 'contract-pdf'], evidence: [] } }
test('candidate authority rejects a different version, unapproved agreement and changed identity', () => {
  assert.equal(candidateAuthority(candidate, agreement), agreement)
  for (const changes of [{ version_number: 3 }, { agreement_id: 'foreign' }, { approval: null }, { identity: { ...identity, contract_number: 'other' } }]) assert.equal(candidateAuthority(candidate, { ...agreement, ...changes }), null)
})

test('source loading pins exact approved candidate and rejects unrelated extraction data', async () => {
  const calls = []
  const loaded = await loadAssociationResources({
    agreementVersion: async (...args) => { calls.push(args); return agreement },
    extractionByDocument: async id => { calls.push(id); return { job_id: id, result: { document: { document_id: id === 'invoice-pdf' ? 'wrong-pdf' : id } } } },
  }, candidate, pkg)
  assert.deepEqual(calls[0], ['agreement', 2])
  assert.equal(calls.filter(item => item === 'contract-pdf').length, 1)
  assert.equal(loaded.agreement, agreement)
  assert.equal(loaded.sources.find(item => item.documentId === 'invoice-pdf').record, null)
  assert.ok(loaded.sources.find(item => item.documentId === 'invoice-pdf').error)
})

test('a stale or unavailable candidate never supplies contract sources for confirmation', async () => {
  const loaded = await loadAssociationResources({ agreementVersion: async () => ({ ...agreement, version_number: 3 }), extractionByDocument: async id => ({ result: { document: { document_id: id } } }) }, candidate, pkg)
  assert.equal(loaded.agreement, null)
  assert.ok(loaded.error)
  assert.deepEqual(loaded.sources.map(item => item.documentId), ['invoice-pdf'])
})

test('signal source paths are explicit, document-side specific and never borrow identifiers', () => {
  assert.deepEqual(associationSignalPaths({ invoice_paths: ['/vendor_name'], contract_paths: ['/landlord/name'] }, 'invoice'), ['/vendor_name'])
  assert.deepEqual(associationSignalPaths({ invoice_paths: ['/vendor_name'], contract_paths: ['/landlord/name'] }, 'contract'), ['/landlord/name'])
  assert.deepEqual(associationSignalPaths({ invoice_paths: ['bad', '/vendor_name', '/vendor_name'] }, 'invoice'), ['/vendor_name'])
  assert.deepEqual(associationSignalPaths({ code: 'unknown' }, 'contract'), [])
})

test('different supporting wording requests review while exact identifier conflicts remain explicit', () => {
  assert.deepEqual(associationSignalResult({ status: 'conflicting', strength: 'supporting' }), { label: 'Different wording · review', tone: 'review' })
  assert.deepEqual(associationSignalResult({ status: 'conflicting', strength: 'exact' }), { label: 'Conflicting reference', tone: 'blocking' })
  assert.deepEqual(associationSignalResult({ status: 'conflicting', strength: 'context' }), { label: 'Coverage needs review', tone: 'review' })
  assert.deepEqual(associationSignalResult({ status: 'missing', strength: 'context' }), { label: 'Missing reference', tone: 'unknown' })
})
