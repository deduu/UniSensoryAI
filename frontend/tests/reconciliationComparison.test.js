import test from 'node:test'
import assert from 'node:assert/strict'
import { buildComparison, comparisonAuthority, comparisonSelectedReference, comparisonCitations, loadComparisonResources } from '../src/paper/reconciliationComparison.js'

const identity = { vendor_id: 'vendor', store_id: 'store', contract_number: '65' }
const agreement = {
  agreement_id: 'agreement', version_number: 2, tenant_id: 'tenant', identity,
  approval: { classification: 'psak73' },
  draft: { effective_from: '2027-01-01', effective_to: '2028-12-31', source_document_ids: ['contract-pdf'],
    terms: { currency: 'IDR', fixed_rent: '100000000000000000.03', rent_type: 'fixed', bank_account: '001',
      installment_schedule: { installments: [{ installment_id: 'first', gross_amount: '50000000000000000.01', coverage_start: '2027-01-01', coverage_end: '2027-12-31', conditions: ['Review handover'] }] },
      withholding_policy: { rate: '0.10', rounding_mode: 'half_up', decimal_places: 0 },
    }, evidence: [],
  },
}
const version = {
  case_id: 'case', version_number: 1, tenant_id: 'tenant',
  package: { identity, invoice: { source_document_id: 'invoice-pdf', fields: { ...identity, currency: 'IDR', subtotal: '50000000000000000.01', total: '45000000000000000.01', installment_id: 'first', bank_account: '001' }, evidence: [] }, tax_invoices: [], supporting_documents: [] },
  assessment: { outcome: 'incomplete', findings: [], agreement_reference: { agreement_id: 'agreement', version_number: 2 } },
}
const selectedAgreement = { ...agreement, status: 'approved' }
const missingCoverage = () => structuredClone({
  ...version,
  package: {
    ...version.package,
    association: {
      agreement_id: 'agreement', version_number: 2, reason: 'Source contract confirmed',
      confirmed_by: 'reviewer', confirmed_at: '2026-10-18T00:00:00Z', invoice_fingerprint: 'a'.repeat(64),
    },
  },
  assessment: { ...version.assessment, agreement_reference: null },
})

test('selected-reference scalar equality is visible independently from saved contract authority', () => {
  const current = missingCoverage()
  for (const name of ['vendor_id', 'store_id', 'contract_number']) current.package.invoice.fields = { ...current.package.invoice.fields, [name]: null }
  const before = structuredClone({ current, selectedAgreement })
  const view = buildComparison(current, selectedAgreement)
  for (const id of ['currency', 'bank']) {
    const row = view.rows.find(item => item.id === id)
    assert.equal(row.valueComparison.status, 'equal')
    assert.equal(row.valueComparison.label, 'Values equal')
    assert.equal(row.status, 'unavailable')
  }
  for (const id of ['vendor_id', 'store_id', 'contract_number']) {
    const row = view.rows.find(item => item.id === id)
    assert.equal(row.valueComparison.status, 'missing_invoice')
    assert.equal(row.valueComparison.label, 'Invoice field missing')
    assert.equal(row.actual[1].value, identity[id])
  }
  assert.equal(view.rows.find(row => row.id === 'vendor_id').label, 'Vendor ID')
  assert.equal(view.rows.find(row => row.id === 'store_id').label, 'Store ID')
  assert.equal(view.agreement, null)
  assert.deepEqual({ current, selectedAgreement }, before)
})

test('literal comparisons keep identifiers exact and require known values from both documents', () => {
  const current = missingCoverage()
  current.package.invoice.fields = { ...current.package.invoice.fields, currency: 'USD', bank_account: '0001', vendor_id: 'Vendor', store_id: '' }
  const view = buildComparison(current, selectedAgreement)
  for (const id of ['currency', 'bank', 'vendor_id']) assert.equal(view.rows.find(row => row.id === id).valueComparison.status, 'different')
  assert.equal(view.rows.find(row => row.id === 'store_id').valueComparison.status, 'missing_invoice')
  const master = structuredClone(selectedAgreement)
  master.draft.terms.bank_account = null
  assert.equal(buildComparison(current, master).rows.find(row => row.id === 'bank').valueComparison.status, 'missing_contract')
  assert.equal(buildComparison(current, { ...master, tenant_id: 'foreign' }).rows.find(row => row.id === 'currency').valueComparison.status, 'unavailable')
})

test('literal values never grade coverage, rent, taxes, payment arithmetic or source diagnostics', () => {
  const view = buildComparison(missingCoverage(), selectedAgreement)
  for (const id of ['period', 'gross', 'withholding', 'vat', 'net', 'conditions']) assert.equal(view.rows.find(row => row.id === id).valueComparison, null)
  assert.ok(!view.rows.some(row => row.status === 'matched'))
})

test('reference-only rows retain blocking and review findings even when literal values are equal', () => {
  const current = missingCoverage()
  const findings = [
    { code: 'currency_mismatch', severity: 'blocking', message: 'Saved currency check requires review' },
    { code: 'agreement_missing', severity: 'blocking', message: 'Coverage is unavailable' },
    { code: 'bank_mismatch', severity: 'review', message: 'Saved account review' },
  ]
  current.assessment = { ...current.assessment, findings }
  const view = buildComparison(current, selectedAgreement)
  assert.equal(view.rows.find(row => row.id === 'currency').valueComparison.status, 'equal')
  assert.equal(view.rows.find(row => row.id === 'currency').status, 'blocking')
  assert.equal(view.rows.find(row => row.id === 'period').status, 'blocking')
  assert.equal(view.rows.find(row => row.id === 'bank').status, 'review')
  assert.deepEqual(view.rows.flatMap(row => row.findings), [findings[0], findings[1], findings[2]])
})

test('confirmed selected reference requires exact approved identity and never becomes assessment authority', () => {
  const current = missingCoverage()
  assert.equal(comparisonSelectedReference(current, selectedAgreement), selectedAgreement)
  assert.equal(comparisonAuthority(current, selectedAgreement), null)
  for (const changes of [
    { version_number: 3 }, { agreement_id: 'other' }, { tenant_id: 'foreign' },
    { identity: { ...identity, vendor_id: 'other' } }, { approval: null }, { status: 'draft' },
  ]) assert.equal(comparisonSelectedReference(current, { ...selectedAgreement, ...changes }), null)
  for (const key of ['confirmed_by', 'confirmed_at', 'invoice_fingerprint']) {
    const unconfirmed = structuredClone(current)
    delete unconfirmed.package.association[key]
    assert.equal(comparisonSelectedReference(unconfirmed, selectedAgreement), null)
  }
})

test('reference-only comparison preserves source decimals, money metadata, fields and missing dates', () => {
  const current = missingCoverage()
  const before = structuredClone({ current, selectedAgreement })
  const view = buildComparison(current, selectedAgreement)
  assert.equal(view.mode, 'reference')
  assert.equal(view.agreement, null)
  assert.equal(view.selectedAgreement, selectedAgreement)
  assert.equal(view.contract, selectedAgreement)
  const gross = view.rows.find(row => row.id === 'gross')
  assert.equal(gross.expected[0].value, '50000000000000000.01')
  assert.equal(gross.actual[0].value, '50000000000000000.01')
  assert.equal(gross.expected[0].monetary, true)
  assert.equal(gross.actual[0].currency, 'IDR')
  assert.equal(view.rows.find(row => row.id === 'bank').expected[0].value, '001')
  assert.equal(view.rows.find(row => row.id === 'withholding').expected[0].value, '0.10')
  assert.equal(view.rows.find(row => row.id === 'period').actual[0].value, undefined)
  assert.equal(view.rows.find(row => row.id === 'vat').expected[0].value, null)
  assert.equal(view.rows.find(row => row.id === 'net').expected[0].value, null)
  assert.ok(view.rows.every(row => ['unavailable', 'unknown'].includes(row.status)))
  assert.deepEqual({ current, selectedAgreement }, before)
})

test('reference-only resources load the confirmed exact contract and both original PDFs', async () => {
  const calls = []
  const master = structuredClone(selectedAgreement)
  master.draft.evidence = [{ document_id: 'contract-pdf', evidence: { field_path: '/installment_schedule/installments/0/gross_amount', source_ids: ['gross'], quote: 'Source rent' } }]
  const api = {
    agreementVersion: async (...args) => { calls.push(args); return master },
    extractionByDocument: async id => { calls.push(id); return record(id, [{ page_number: 7, text_blocks: [{ block_id: 'gross', text: 'Source rent' }] }]) },
  }
  const loaded = await loadComparisonResources(api, missingCoverage())
  assert.deepEqual(calls, [['agreement', 2], 'invoice-pdf', 'contract-pdf'])
  assert.equal(loaded.agreement, null)
  assert.equal(loaded.selectedAgreement, master)
  assert.deepEqual(loaded.sources.map(source => source.documentId), ['invoice-pdf', 'contract-pdf'])
  const view = buildComparison(missingCoverage(), loaded.selectedAgreement)
  const gross = view.rows.find(row => row.id === 'gross')
  const links = comparisonCitations(loaded.sources, gross.contractPaths, view.contract.draft.evidence, view.contract.draft.source_document_ids, true)
  assert.deepEqual(links.map(link => [link.documentId, link.page]), [['contract-pdf', 7]])
})

test('wrong or unapproved selected references expose neither contract values nor contract sources', async () => {
  for (const changes of [{ approval: null }, { status: 'draft' }, { version_number: 3 }, { tenant_id: 'foreign' }]) {
    const wrong = { ...selectedAgreement, ...changes }
    const loaded = await loadComparisonResources({
      agreementVersion: async () => wrong,
      extractionByDocument: async id => record(id),
    }, missingCoverage())
    assert.equal(loaded.selectedAgreement, null)
    assert.ok(loaded.agreementError)
    assert.deepEqual(loaded.sources.map(source => source.documentId), ['invoice-pdf'])
    const view = buildComparison(missingCoverage(), wrong)
    assert.equal(view.mode, 'unavailable')
    assert.ok(view.rows.every(row => row.expected.every(item => item.value == null)))
  }
})

test('stored payment narrative and source pricing diagnostics remain exact and separate from saved findings', () => {
  const current = missingCoverage()
  current.assessment.findings = [
    { code: 'missing_tax_invoice', severity: 'blocking', message: 'Tax invoice needed' },
    { code: 'missing_field', severity: 'blocking', field_path: '/invoice/fields/service_period_start', message: 'Start needed' },
    { code: 'missing_field', severity: 'blocking', field_path: '/invoice/fields/service_period_end', message: 'End needed' },
    { code: 'agreement_missing', severity: 'blocking', message: 'Coverage needed' },
  ]
  const master = structuredClone(selectedAgreement)
  delete master.draft.terms.installment_schedule
  delete master.draft.terms.withholding_policy
  const narrative = 'Pembayaran pertama Rp 546.296.295,00.\n  Semua dokumen harus diterima lengkap.'
  master.draft.terms.payment_schedule = narrative
  const diagnostic = { code: 'source_amount_discrepancy', field_path: '/fixed_rent', message: 'Retained source difference: IDR 3.00. Verify the original amounts.' }
  master.draft.extraction_warnings = [diagnostic, { code: 'source_text_review_required', field_path: '/payment_schedule', message: 'Inspect the full clauses' }]
  const before = structuredClone({ current, master })
  const view = buildComparison(current, master)
  const conditions = view.rows.find(row => row.id === 'conditions')
  assert.equal(conditions.expected.find(item => item.label === 'Source payment schedule').value, narrative)
  assert.ok(conditions.contractPaths.includes('/payment_schedule'))
  assert.equal(conditions.expected.find(item => item.label === 'Installment conditions').value, undefined)
  const pricing = view.rows.find(row => row.id === 'source_pricing')
  assert.equal(pricing.kind, 'contract_diagnostic')
  assert.equal(pricing.expected[0].label, 'Retained contract diagnostic')
  assert.equal(pricing.expected[0].value, diagnostic.message)
  assert.deepEqual(pricing.contractPaths, ['/fixed_rent'])
  assert.deepEqual(pricing.contractDiagnostics, [diagnostic])
  assert.deepEqual(pricing.findings, [])
  assert.equal(pricing.status, 'unavailable')
  assert.equal(view.rows.find(row => row.id === 'withholding').expected[0].value, undefined)
  const savedFindings = [...view.rows.flatMap(row => row.findings), ...view.otherFindings]
  assert.equal(savedFindings.length, 4)
  assert.ok(current.assessment.findings.every(finding => savedFindings.includes(finding)))
  assert.deepEqual({ current, master }, before)
})

test('payment narrative citations expose their exact source page and invalid contract context hides diagnostics', () => {
  const master = structuredClone(selectedAgreement)
  master.draft.terms.payment_schedule = 'Source payment prerequisites'
  master.draft.extraction_warnings = [{ code: 'source_amount_discrepancy', field_path: '/fixed_rent', message: 'Source amount differs' }]
  master.draft.evidence = [{ document_id: 'contract-pdf', evidence: { field_path: '/payment_schedule', source_ids: ['payment'], quote: 'Source payment prerequisites' } }]
  const sources = [{ documentId: 'contract-pdf', record: record('contract-pdf', [{ page_number: 17, text_blocks: [{ block_id: 'payment', text: 'Source payment prerequisites' }] }]) }]
  const view = buildComparison(missingCoverage(), master)
  const conditions = view.rows.find(row => row.id === 'conditions')
  const links = comparisonCitations(sources, conditions.contractPaths, master.draft.evidence, master.draft.source_document_ids, true)
  assert.deepEqual(links.map(link => link.page), [17])
  const unavailable = buildComparison(missingCoverage(), { ...master, tenant_id: 'foreign' })
  assert.ok(!unavailable.rows.some(row => row.id === 'source_pricing'))
  const authoritative = buildComparison(version, master)
  assert.equal(authoritative.rows.find(row => row.id === 'source_pricing').status, 'unknown')
})

test('assessment authority takes precedence and a present invalid or failed reference never falls back', async () => {
  const selected = missingCoverage()
  const authoritative = { ...selected, assessment: version.assessment }
  const view = buildComparison(authoritative, selectedAgreement)
  assert.equal(view.mode, 'authority')
  assert.equal(view.agreement, selectedAgreement)
  assert.equal(view.selectedAgreement, null)
  for (const ref of [version.assessment.agreement_reference, {}, false]) {
    const current = { ...selected, assessment: { ...selected.assessment, agreement_reference: ref } }
    const calls = []
    const loaded = await loadComparisonResources({
      agreementVersion: async (...args) => { calls.push(args); throw new Error('Unavailable') },
      extractionByDocument: async id => record(id),
    }, current)
    assert.equal(calls.length, 1)
    assert.equal(loaded.agreement, null)
    assert.equal(loaded.selectedAgreement, null)
    assert.deepEqual(loaded.sources.map(source => source.documentId), ['invoice-pdf'])
    assert.equal(comparisonSelectedReference(current, selectedAgreement), null)
  }
})

test('authority must be the approved exact version and same tenant/identity', () => {
  assert.equal(comparisonAuthority(version, agreement), agreement)
  for (const changes of [{ version_number: 3 }, { tenant_id: 'foreign' }, { approval: null }, { agreement_id: 'other' }, { identity: { ...identity, store_id: 'other' } }]) {
    assert.equal(comparisonAuthority(version, { ...agreement, ...changes }), null)
  }
  assert.equal(comparisonAuthority({ ...version, assessment: { ...version.assessment, agreement_reference: null } }, agreement), null)
})

test('comparison keeps exact decimals and installment expectations separate from annual rent', () => {
  const before = structuredClone({ version, agreement })
  const view = buildComparison(version, agreement)
  const gross = view.rows.find(row => row.id === 'gross')
  assert.equal(gross.expected[0].value, '50000000000000000.01')
  assert.equal(gross.actual[0].value, '50000000000000000.01')
  assert.equal(gross.status, 'reported')
  assert.ok(!view.rows.some(row => row.status === 'matched'))
  assert.deepEqual({ version, agreement }, before)
})

test('money metadata keeps each source currency and leaves rates and bank IDs untouched', () => {
  const master = structuredClone(agreement)
  master.draft.terms.installment_schedule.currency = 'USD'
  const view = buildComparison(version, master)
  const gross = view.rows.find(row => row.id === 'gross')
  assert.equal(gross.expected[0].monetary, true)
  assert.equal(gross.expected[0].currency, 'USD')
  assert.equal(gross.actual[0].currency, 'IDR')
  assert.equal(view.rows.find(row => row.id === 'bank').expected[0].monetary, undefined)
  assert.equal(view.rows.find(row => row.id === 'withholding').expected[0].monetary, undefined)
  assert.equal(view.rows.find(row => row.id === 'net').actual[0].monetary, true)
})

test('reviewed allocation is labelled separately and never fills missing source dates', () => {
  const pkg = { ...version.package, review_context: { allocation_start: '2027-01-01', allocation_end: '2027-12-31' } }
  const row = buildComparison({ ...version, package: pkg }, agreement).rows.find(row => row.id === 'period')
  assert.equal(row.actual.find(item => item.label === 'Source start').value, undefined)
  assert.equal(row.actual.find(item => item.label === 'Reviewed allocation start').value, '2027-01-01')
})

test('an absent or invalid installment never substitutes the annual fixed rent as expected gross', () => {
  for (const installment_id of [undefined, 'not-in-schedule']) {
    const pkg = { ...version.package, invoice: { ...version.package.invoice, fields: { ...version.package.invoice.fields, installment_id } } }
    const row = buildComparison({ ...version, package: pkg }, agreement).rows.find(item => item.id === 'gross')
    assert.equal(row.expected[0].value, undefined)
    assert.equal(row.status, 'unknown')
    assert.ok(!row.expected.some(item => item.value === agreement.draft.terms.fixed_rent))
  }
})

test('legacy invoice comparison retains signed-tax arithmetic instead of inventing structured components', () => {
  const legacy = structuredClone(agreement)
  delete legacy.draft.terms.installment_schedule
  delete legacy.draft.terms.withholding_policy
  const row = buildComparison(version, legacy).rows.find(item => item.id === 'net')
  assert.equal(row.expected[0].value, 'Subtotal + signed tax adjustment = total')
})

test('saved installment codes map by meaning, generic findings respect owning document, new codes remain visible', () => {
  const findings = [
    { code: 'installment_amount_mismatch', severity: 'blocking', field_path: '/invoice/fields/installment_id', source_document_ids: ['invoice-pdf'], message: 'Gross differs' },
    { code: 'bank_mismatch', severity: 'blocking', field_path: '/fields/bank_account', source_document_ids: ['tax-pdf'], message: 'Attachment bank differs' },
    { code: 'missing_field', severity: 'blocking', field_path: '/invoice/fields/currency', source_document_ids: ['invoice-pdf'], message: 'Currency needed' },
    { code: 'future_custom_rule', severity: 'review', message: 'New rule' },
  ]
  const view = buildComparison({ ...version, assessment: { ...version.assessment, findings } }, agreement)
  assert.equal(view.rows.find(row => row.id === 'gross').status, 'blocking')
  assert.equal(view.rows.find(row => row.id === 'bank').findings.length, 0)
  assert.equal(view.rows.find(row => row.id === 'currency').status, 'blocking')
  assert.deepEqual(view.otherFindings.map(item => item.code), ['bank_mismatch', 'future_custom_rule'])
})

test('unavailable authority cannot show expectations from an unrelated agreement or a clean row result', () => {
  const view = buildComparison(version, { ...agreement, version_number: 3 })
  assert.equal(view.agreement, null)
  assert.ok(view.rows.every(row => row.expected.every(item => item.value == null)))
  assert.ok(view.rows.every(row => row.status !== 'reported'))
})

const record = (id, pages = []) => ({ job_id: `${id}-job`, filename: `${id}.pdf`, result: { document: { document_id: id, pages } } })
test('citations retain all unique pages, document ownership, quotes and unresolved references', () => {
  const resources = [{ documentId: 'contract-pdf', record: record('contract-pdf', [
    { page_number: 3, text_blocks: [{ block_id: 'a' }, { block_id: 'repeated' }] },
    { page_number: 8, text_blocks: [{ block_id: 'b' }, { block_id: 'repeated' }] },
  ]) }]
  const evidence = [
    { document_id: 'contract-pdf', evidence: { field_path: '/fixed_rent', source_ids: ['a', 'b', 'repeated'], quote: 'Approved rent' } },
    { document_id: 'other-pdf', evidence: { field_path: '/fixed_rent', source_ids: ['a'], quote: 'Foreign' } },
    { evidence: { field_path: '/fixed_rent', source_ids: ['a'], quote: 'Unqualified' } },
  ]
  const links = comparisonCitations(resources, ['/fixed_rent'], evidence, ['contract-pdf'], true)
  assert.deepEqual(links.map(link => [link.documentId, link.page]), [['contract-pdf', 3], ['contract-pdf', 8]])
  assert.deepEqual(links[0].quotes.map(item => item.quote), ['Approved rent'])
  assert.deepEqual(links[0].unresolved, ['repeated'])
  assert.deepEqual(comparisonCitations(resources, ['/fixed_rent'], evidence, ['invoice-pdf'], true), [])
})

test('resource loading pins authority, deduplicates sources and rejects wrong-document responses', async () => {
  const calls = []
  const api = {
    agreementVersion: async (...args) => { calls.push(args); return agreement },
    extractionByDocument: async id => { calls.push(id); return record(id === 'invoice-pdf' ? 'wrong-pdf' : id) },
  }
  const loaded = await loadComparisonResources(api, version)
  assert.deepEqual(calls[0], ['agreement', 2])
  assert.equal(loaded.agreement, agreement)
  assert.equal(loaded.sources.find(item => item.documentId === 'invoice-pdf').record, null)
  assert.ok(loaded.sources.find(item => item.documentId === 'invoice-pdf').error)
  assert.equal(loaded.sources.find(item => item.documentId === 'contract-pdf').record.result.document.document_id, 'contract-pdf')
})

test('missing agreement or PDF is recoverable and does not discard invoice fields', async () => {
  const api = { agreementVersion: async () => { throw new Error('Unavailable') }, extractionByDocument: async id => record(id) }
  const loaded = await loadComparisonResources(api, version)
  assert.equal(loaded.agreement, null)
  assert.ok(loaded.agreementError)
  assert.equal(loaded.sources.length, 1)
  assert.equal(loaded.sources[0].documentId, 'invoice-pdf')
})
