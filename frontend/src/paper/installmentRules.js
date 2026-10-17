import { createSampleAgreement, createSamplePackage } from './helpers.js'

const clone = value => JSON.parse(JSON.stringify(value))
const COMPONENTS = ['subtotal', 'vat_amount', 'withholding_amount', 'rounding_adjustment', 'total']
const DECIMAL = /^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$/

/** Saved obligation IDs are stable across revisions, including JSON imports. */
export function assertSavedInstallmentIds(terms, savedIds = []) {
  const nextIds = (terms.installment_schedule?.installments || []).map(item => item.installment_id)
  if (savedIds.some(id => !nextIds.includes(id))) throw new Error('Saved installment IDs cannot be removed or renamed. Correct amounts or conditions in a new version while retaining each saved ID.')
  return terms
}

/** Update a reviewed nested rule without discarding unrelated source attributes. */
export function patchPaymentRule(terms, key, changes) {
  return { ...terms, [key]: { ...(terms[key] || {}), ...changes } }
}

/** Edit a single cash installment without changing the source pricing basis. */
export function patchInstallment(terms, index, changes) {
  return patchPaymentRule(terms, 'installment_schedule', {
    installments: (terms.installment_schedule?.installments || []).map((item, position) => position === index ? { ...item, ...changes } : item),
  })
}

/** Remove only the explicitly selected installment from the unsaved draft. */
export function removeInstallment(terms, index) {
  return patchPaymentRule(terms, 'installment_schedule', {
    installments: (terms.installment_schedule?.installments || []).filter((_, position) => position !== index),
  })
}

function scaled(value, scale) {
  const [whole, fraction = ''] = value.replace(/^-/, '').split('.')
  const result = BigInt(`${whole}${fraction.padEnd(scale, '0')}`)
  return value.startsWith('-') ? -result : result
}

function decimal(value, scale) {
  const sign = value < 0n ? '-' : ''
  const text = String(value < 0n ? -value : value).padStart(scale + 1, '0')
  if (!scale) return `${sign}${text}`
  return `${sign}${text.slice(0, -scale)}.${text.slice(-scale)}`.replace(/\.?0+$/, '')
}

/** Preview exact component arithmetic; server rules remain authoritative. */
export function invoicePaymentArithmetic(fields = {}) {
  const missing = COMPONENTS.filter(key => fields[key] == null || fields[key] === '')
  const invalid = COMPONENTS.filter(key => fields[key] != null && fields[key] !== '' && (typeof fields[key] !== 'string' || !DECIMAL.test(fields[key]) || fields[key].length > 128))
  if (missing.length || invalid.length) return { missing, invalid, expectedTotal: null, matches: null, legacyTaxMatches: null }
  const values = COMPONENTS.map(key => fields[key])
  const legacyValid = typeof fields.tax_amount === 'string' && DECIMAL.test(fields.tax_amount) && fields.tax_amount.length <= 128
  const scale = Math.max(...[...values, ...(legacyValid ? [fields.tax_amount] : [])].map(value => value.split('.')[1]?.length || 0))
  const [gross, vat, withheld, rounding, net] = values.map(value => scaled(value, scale))
  const expected = gross + vat - withheld + rounding
  return { missing, invalid, expectedTotal: decimal(expected, scale), matches: expected === net, legacyTaxMatches: legacyValid ? scaled(fields.tax_amount, scale) === vat - withheld : null }
}

/** Copy an explicitly chosen allocation separately from source invoice dates. */
export function applyReviewedAllocation(pkg, agreement, installmentId) {
  const installment = agreement?.draft?.terms?.installment_schedule?.installments?.find(item => item.installment_id === installmentId)
  if (!installment) throw new Error('Select an installment from the agreement schedule first.')
  return {
    ...pkg,
    invoice: { ...pkg.invoice, fields: { ...pkg.invoice.fields, installment_id: installmentId } },
    review_context: {
      ...(pkg.review_context || {}), allocation_start: installment.coverage_start,
      allocation_end: installment.coverage_end, reason: pkg.review_context?.reason || '',
      source_document_ids: [...(agreement.draft.source_document_ids || [])],
    },
  }
}

/** A changed obligation needs its own explicit allocation review. */
export function selectInvoiceInstallment(pkg, installmentId) {
  return {
    ...pkg, invoice: { ...pkg.invoice, fields: { ...pkg.invoice.fields, installment_id: installmentId || null } },
    ...(installmentId !== (pkg.invoice.fields.installment_id || '') && pkg.review_context ? { review_context: null } : {}),
  }
}

/** Isolated synthetic master for testing annual prices paid in installments. */
export function createInstallmentDemoAgreement() {
  const result = createSampleAgreement()
  result.identity.contract_number = result.identity.contract_number.replace('DEMO-RA-', 'DEMO-INSTALLMENT-')
  result.draft.terms = {
    ...result.draft.terms, ...result.identity,
    vendor_name: 'Synthetic installment landlord',
    lease_start_date: '2027-01-05', lease_end_date: '2032-01-04', lease_duration_months: 60,
    payment_schedule: 'Synthetic example: two advance cash installments; source conditions require separate review.',
    fixed_rent: '327777777', extensions: { fixed_rent_basis: 'annual' },
    installment_schedule: {
      schedule_id: 'synthetic-two-stage-rent', version: '1', currency: 'IDR', total_gross: '1638888888',
      source_reference: 'Synthetic UI scenario, not source document evidence.',
      source_discrepancy_note: 'Synthetic review scenario: the stated total exceeds annual rent multiplied by five by IDR 3. Preserve the stated installment amounts.',
      installments: [
        { installment_id: 'stage-1', gross_amount: '983333333', coverage_start: '2027-01-05', coverage_end: '2032-01-04', conditions: ['Synthetic test: verify complete invoice and signature conditions before payment.'] },
        { installment_id: 'stage-2', gross_amount: '655555555', coverage_start: '2027-01-05', coverage_end: '2032-01-04', conditions: ['Synthetic test: verify the second installment trigger and required documents.'] },
      ],
    },
    withholding_policy: { policy_id: 'synthetic-rent-withholding', version: '1', rate: '0.1', rounding_mode: 'down', decimal_places: 0, source_reference: 'Synthetic reviewed policy for local arithmetic testing; not a tax determination.' },
  }
  result.draft.effective_from = '2027-01-05'
  result.draft.effective_to = '2032-01-04'
  result.draft.change_reason = 'Synthetic installment and withholding UI scenario; review and approve explicitly.'
  return result
}

/** Synthetic package only; never add these documents to a real invoice. */
export function createInstallmentDemoPackage(agreement) {
  const master = agreement || createInstallmentDemoAgreement()
  if (!master.identity.vendor_id.startsWith('DEMO-') || !master.identity.contract_number.startsWith('DEMO-INSTALLMENT-') || master.draft.terms.installment_schedule?.schedule_id !== 'synthetic-two-stage-rent') throw new Error('Use a synthetic installment demo agreement before loading synthetic supporting documents.')
  const result = createSamplePackage(master.identity)
  const fields = result.invoice.fields
  Object.assign(fields, {
    invoice_date: '2026-10-15', service_period_start: null, service_period_end: null,
    installment_id: 'stage-1', subtotal: '983333333', vat_amount: '0', withholding_amount: '98333333',
    rounding_adjustment: '0', tax_amount: '-98333333', total: '885000000',
    description: 'Synthetic stage-one advance rent; amounts adapted for local testing, not original source evidence.',
  })
  result.tax_invoices = []
  result.supporting_documents = [{
    source_document_id: result.invoice.source_document_id.replace('demo-invoice-', 'demo-withholding-certificate-'),
    fields: { ...master.identity, document_type: 'withholding_certificate', reference_number: `DEMO-WHT-${fields.invoice_number}`, invoice_number: fields.invoice_number, document_date: fields.invoice_date, currency: fields.currency, total: fields.withholding_amount, description: 'Synthetic withholding certificate fields for local testing only. This is not a real tax document.' },
    evidence: [], warnings: [],
  }]
  result.review_context = {
    allocation_start: '2027-01-05', allocation_end: '2032-01-04',
    reason: 'Synthetic test allocation reviewed against the synthetic installment schedule; source invoice service dates remain unknown.',
    source_document_ids: [...master.draft.source_document_ids],
  }
  return clone(result)
}
