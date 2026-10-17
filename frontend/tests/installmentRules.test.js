import test from 'node:test'
import assert from 'node:assert/strict'
import {
  applyReviewedAllocation, assertSavedInstallmentIds, createInstallmentDemoAgreement, createInstallmentDemoPackage,
  invoicePaymentArithmetic, patchInstallment, patchPaymentRule, removeInstallment, selectInvoiceInstallment,
} from '../src/paper/installmentRules.js'
import { parseStructuredValue } from '../src/paper/helpers.js'

test('nullable nested rules retain unknown instead of replacing null with an empty object', () => {
  assert.equal(parseStructuredValue('null', { type: 'object', nullable: true }), null)
  assert.equal(parseStructuredValue('null', { type: 'array', nullable: true }), null)
  assert.throws(() => parseStructuredValue('null', { type: 'object' }), /object/i)
  assert.throws(() => parseStructuredValue('[]', { type: 'object' }), /object/i)
  assert.deepEqual(parseStructuredValue('{"future":{"retained":true}}', { type: 'object' }), { future: { retained: true } })
})

test('editing one schedule item preserves sibling rules, unknown values, and caller ownership', () => {
  const terms = { installment_schedule: { schedule_id: 's', future: { kept: true }, installments: [{ installment_id: 'one', gross_amount: null, conditions: ['A AND B'] }, { installment_id: 'two', gross_amount: '2' }] }, withholding_policy: null, extensions: { custom: true } }
  const changed = patchInstallment(terms, 0, { gross_amount: '12345678901234567890.001' })
  assert.equal(changed.installment_schedule.installments[0].gross_amount, '12345678901234567890.001')
  assert.deepEqual(changed.installment_schedule.installments[0].conditions, ['A AND B'])
  assert.deepEqual(changed.installment_schedule.future, { kept: true })
  assert.equal(changed.withholding_policy, null)
  assert.deepEqual(changed.extensions, terms.extensions)
  assert.equal(terms.installment_schedule.installments[0].gross_amount, null)
  assert.equal(removeInstallment(changed, 0).installment_schedule.installments[0].installment_id, 'two')
  assert.deepEqual(patchPaymentRule(terms, 'withholding_policy', { rate: '0.1' }).withholding_policy, { rate: '0.1' })
})

test('component arithmetic uses exact decimal strings and never deducts legacy signed tax twice', () => {
  const result = invoicePaymentArithmetic({ subtotal: '983333333', vat_amount: '0', withholding_amount: '98333333', rounding_adjustment: '0', total: '885000000', tax_amount: '-98333333' })
  assert.equal(result.expectedTotal, '885000000')
  assert.equal(result.matches, true)
  assert.equal(result.legacyTaxMatches, true)
  assert.equal(invoicePaymentArithmetic({ subtotal: '9007199254740993.01', vat_amount: '0.02', withholding_amount: '0.01', rounding_adjustment: '-0.001', total: '9007199254740993.019' }).matches, true)
})

test('unknown components remain unknown and invalid decimal text never becomes zero', () => {
  const fields = { subtotal: '100', vat_amount: null, withholding_amount: '10', rounding_adjustment: null, total: '90' }
  assert.equal(invoicePaymentArithmetic(fields).expectedTotal, null)
  assert.deepEqual(invoicePaymentArithmetic(fields).missing, ['vat_amount', 'rounding_adjustment'])
  assert.equal(invoicePaymentArithmetic({ ...fields, vat_amount: 'NaN', rounding_adjustment: '0' }).expectedTotal, null)
  assert.equal(invoicePaymentArithmetic({ ...fields, vat_amount: '0', rounding_adjustment: '0', total: '91' }).matches, false)
})

test('explicit reviewed allocation does not manufacture source service dates or evidence', () => {
  const agreement = createInstallmentDemoAgreement()
  const pkg = createInstallmentDemoPackage(agreement)
  pkg.review_context = { reason: 'Reviewed complete source clauses.', future: true }
  const before = structuredClone(pkg)
  const next = applyReviewedAllocation(pkg, agreement, 'stage-2')
  assert.equal(next.invoice.fields.installment_id, 'stage-2')
  assert.equal(next.invoice.fields.service_period_start, null)
  assert.equal(next.invoice.fields.service_period_end, null)
  assert.deepEqual(next.invoice.evidence, before.invoice.evidence)
  assert.equal(next.review_context.allocation_start, '2027-01-05')
  assert.equal(next.review_context.allocation_end, '2032-01-04')
  assert.equal(next.review_context.reason, 'Reviewed complete source clauses.')
  assert.equal(next.review_context.future, true)
  assert.deepEqual(next.review_context.source_document_ids, agreement.draft.source_document_ids)
  assert.deepEqual(pkg, before)
  assert.throws(() => applyReviewedAllocation(pkg, agreement, 'missing'), /installment/i)
})

test('changing the installment clears stale reviewed allocation while retaining source data', () => {
  const agreement = createInstallmentDemoAgreement()
  const pkg = createInstallmentDemoPackage(agreement)
  const next = selectInvoiceInstallment(pkg, 'stage-2')
  assert.equal(next.review_context, null)
  assert.equal(next.invoice.fields.installment_id, 'stage-2')
  assert.equal(next.invoice.fields.service_period_start, null)
  assert.equal(next.invoice.fields.withholding_amount, pkg.invoice.fields.withholding_amount)
  assert.deepEqual(next.supporting_documents, pkg.supporting_documents)
  assert.deepEqual(selectInvoiceInstallment(pkg, 'stage-1').review_context, pkg.review_context)
  assert.equal(selectInvoiceInstallment(pkg, '').invoice.fields.installment_id, null)
})

test('synthetic installment fixtures are isolated, identified, and do not mimic real evidence', () => {
  const first = createInstallmentDemoAgreement()
  const second = createInstallmentDemoAgreement()
  assert.notEqual(first.identity.vendor_id, second.identity.vendor_id)
  assert.match(first.identity.vendor_id, /^DEMO-/)
  assert.match(first.draft.change_reason, /synthetic/i)
  assert.deepEqual(first.draft.evidence, [])
  const pkg = createInstallmentDemoPackage(first)
  assert.deepEqual(pkg.identity, first.identity)
  assert.equal(pkg.invoice.fields.installment_id, 'stage-1')
  assert.equal(pkg.invoice.fields.tax_amount, '-98333333')
  assert.deepEqual(pkg.tax_invoices, [])
  assert.equal(pkg.supporting_documents[0].fields.document_type, 'withholding_certificate')
  assert.match(pkg.supporting_documents[0].fields.description, /synthetic/i)
  assert.match(pkg.invoice.fields.invoice_number, /^DEMO-/)
  assert.deepEqual(pkg.review_context.source_document_ids, first.draft.source_document_ids)
  assert.equal(invoicePaymentArithmetic(pkg.invoice.fields).matches, true)
  pkg.identity.vendor_id = 'changed'
  assert.notEqual(first.identity.vendor_id, 'changed')
  const realIdentity = structuredClone(first)
  realIdentity.identity.vendor_id = 'REAL-VENDOR'
  assert.throws(() => createInstallmentDemoPackage(realIdentity), /synthetic/i)
})

test('saved installment IDs cannot be removed or renamed through the advanced editor', () => {
  assert.doesNotThrow(() => assertSavedInstallmentIds({ installment_schedule: { installments: [{ installment_id: 'one', gross_amount: '99' }, { installment_id: 'new' }] } }, ['one']))
  assert.throws(() => assertSavedInstallmentIds({ installment_schedule: null }, ['one']), /saved.*IDs/i)
  assert.throws(() => assertSavedInstallmentIds({ installment_schedule: { installments: [{ installment_id: 'changed' }] } }, ['one']), /saved.*IDs/i)
})
