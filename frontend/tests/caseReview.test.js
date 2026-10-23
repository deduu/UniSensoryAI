import test from 'node:test'
import assert from 'node:assert/strict'
import { reviewEligibility, uniqueFindingCodes, replacePackage, applyPackageIdentity } from '../src/paper/caseReview.js'

const context = { can_decide_cases: true, user_id: 'reviewer', override_codes: ['bank_mismatch'] }
const version = { version_number: 2, created_by: 'author', assessment: { findings: [], agreement_reference: { agreement_id: 'ref' } } }

test('saved assessment requires reassessment after the active field policy changes', () => {
  const old = { ...version, assessment: { ...version.assessment, policy_id: 'policy', policy_version: 'v1' } }
  const current = { ...context, policy_id: 'policy', policy_version: 'v2' }
  const eligibility = reviewEligibility(old, 2, current)
  assert.equal(eligibility.canApprove, false)
  assert.equal(eligibility.canDecide, false)
  assert.match(eligibility.reason, /requirements.*changed|policy.*changed/i)
  assert.equal(reviewEligibility(old, 2, { ...current, policy_version: 'v1' }).canApprove, true)
})

test('approval requires a current undecided version and authoritative agreement', () => {
  assert.equal(reviewEligibility(version, 2, context).canApprove, true)
  assert.equal(reviewEligibility(version, 3, context).canApprove, false)
  assert.equal(reviewEligibility({ ...version, decision: { action: 'approve' } }, 2, context).canDecide, false)
  assert.equal(reviewEligibility({ ...version, assessment: { findings: [] } }, 2, context).canApprove, false)
  assert.equal(reviewEligibility({ ...version, duplicate_of: 'original' }, 2, context).canApprove, false)
})

test('permission and independent review gate both dispositions', () => {
  assert.equal(reviewEligibility(version, 2, { ...context, can_decide_cases: false }).canDecide, false)
  assert.equal(reviewEligibility(version, 2, { ...context, user_id: 'author', require_independent_case_approval: true }).canDecide, false)
})

test('every distinct unresolved code needs explicit acceptance; structural findings stay blocked', () => {
  const bank = { ...version, assessment: { ...version.assessment, findings: [{ code: 'bank_mismatch' }, { code: 'bank_mismatch' }] } }
  assert.deepEqual(uniqueFindingCodes(bank), ['bank_mismatch'])
  assert.equal(reviewEligibility(bank, 2, context).canApprove, false)
  assert.equal(reviewEligibility(bank, 2, context, ['bank_mismatch']).canApprove, true)
  assert.equal(reviewEligibility(bank, 2, context, ['bank_mismatch', 'unrelated']).canApprove, false)
  const incomplete = { ...bank, assessment: { ...bank.assessment, findings: [{ code: 'missing_document' }] } }
  assert.equal(reviewEligibility(incomplete, 2, context, ['missing_document']).canApprove, false)
  assert.equal(reviewEligibility(incomplete, 2, context).canDecide, true)
})

test('replacement import clears omitted document collections without touching provenance', () => {
  const imported = { identity: { vendor_id: 'v' }, invoice: { fields: {}, evidence: [{ page: 1 }] } }
  const result = replacePackage(imported)
  assert.deepEqual(result.tax_invoices, [])
  assert.deepEqual(result.utility_statements, [])
  assert.deepEqual(result.supporting_documents, [])
  assert.deepEqual(result.invoice.evidence, [{ page: 1 }])
  result.invoice.evidence[0].page = 2
  assert.equal(imported.invoice.evidence[0].page, 1)
})

test('identity assignment never copies master IDs into extracted document fields', () => {
  const old = { vendor_id: 'v1', store_id: 's1', contract_number: 'c1' }
  const identity = { vendor_id: 'v2', store_id: 's2', contract_number: 'c2' }
  const pkg = { identity: old, invoice: { fields: { ...old, invoice_number: '001' } }, tax_invoices: [{ fields: { ...old, vendor_id: 'other-source-vendor' }, evidence: [{ quote: 'retained' }] }], supporting_documents: [{ fields: {} }] }
  const result = applyPackageIdentity(pkg, identity)
  assert.equal(result.invoice.fields.vendor_id, 'v1')
  assert.equal(result.invoice.fields.invoice_number, '001')
  assert.equal(result.tax_invoices[0].fields.vendor_id, 'other-source-vendor')
  assert.equal(result.tax_invoices[0].fields.store_id, 's1')
  assert.equal(result.supporting_documents[0].fields.contract_number, undefined)
  assert.deepEqual(result.identity, identity)
  assert.deepEqual(result.tax_invoices[0].evidence, pkg.tax_invoices[0].evidence)
  assert.equal(pkg.invoice.fields.vendor_id, 'v1')
})
