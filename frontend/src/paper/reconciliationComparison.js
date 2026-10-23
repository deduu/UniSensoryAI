import { fieldEvidencePages } from './sourceReview.js'

const IDENTITY = ['vendor_id', 'store_id', 'contract_number']
const LITERAL_FIELDS = new Set([...IDENTITY, 'currency', 'bank'])
const known = value => value !== undefined && value !== null && value !== ''
const field = (label, value) => ({ label, value })
const moneyField = (label, value, currency) => ({ label, value, monetary: true, currency })
const hasAssessmentReference = version => version?.assessment?.agreement_reference !== undefined && version.assessment.agreement_reference !== null

/** Compare only like-for-like source strings, independently of saved financial checks. */
function storedValueComparison(row, contract) {
  if (!LITERAL_FIELDS.has(row.id)) return null
  if (!contract) return { status: 'unavailable', label: 'Contract unavailable' }
  const expected = row.expected[0]?.value
  const actual = row.actual[0]?.value
  if (!known(expected) && !known(actual)) return { status: 'missing_both', label: 'Both fields missing' }
  if (!known(actual)) return { status: 'missing_invoice', label: 'Invoice field missing' }
  if (!known(expected)) return { status: 'missing_contract', label: 'Contract field missing' }
  return actual === expected ? { status: 'equal', label: 'Values equal' } : { status: 'different', label: 'Values differ' }
}

function confirmedSelection(version) {
  if (hasAssessmentReference(version)) return null
  const selection = version?.package?.association
  return typeof selection?.agreement_id === 'string' && selection.agreement_id.trim()
    && Number.isInteger(selection.version_number) && selection.version_number > 0
    && typeof selection.confirmed_by === 'string' && selection.confirmed_by.trim()
    && typeof selection.confirmed_at === 'string' && /(?:Z|[+-]\d{2}:\d{2})$/u.test(selection.confirmed_at) && Number.isFinite(Date.parse(selection.confirmed_at))
    && typeof selection.invoice_fingerprint === 'string' && /^[a-f0-9]{64}$/u.test(selection.invoice_fingerprint) ? selection : null
}

/** Accept only the exact approved authority pinned to this historical assessment. */
export function comparisonAuthority(version, candidate) {
  const ref = version?.assessment?.agreement_reference
  return ref && candidate?.approval && candidate.agreement_id === ref.agreement_id
    && candidate.version_number === ref.version_number && candidate.tenant_id === version.tenant_id
    && IDENTITY.every(key => candidate.identity?.[key] === version.package?.identity?.[key]) ? candidate : null
}

/** A confirmed selection locates source material; it never establishes invoice coverage. */
export function comparisonSelectedReference(version, candidate) {
  const selection = confirmedSelection(version)
  return selection && candidate?.approval && candidate.status === 'approved'
    && candidate.agreement_id === selection.agreement_id && candidate.version_number === selection.version_number
    && typeof version.tenant_id === 'string' && version.tenant_id.trim() && candidate.tenant_id === version.tenant_id
    && IDENTITY.every(key => typeof version.package?.identity?.[key] === 'string' && version.package.identity[key].trim() && candidate.identity?.[key] === version.package.identity[key]) ? candidate : null
}

/** Present literal source comparisons and saved findings without reproducing accounting rules. */
export function buildComparison(version, candidate) {
  const agreement = comparisonAuthority(version, candidate)
  const selectedAgreement = agreement ? null : comparisonSelectedReference(version, candidate)
  const contract = agreement || selectedAgreement
  const mode = agreement ? 'authority' : selectedAgreement ? 'reference' : 'unavailable'
  const pkg = version.package
  const invoice = pkg.invoice.fields
  const terms = contract?.draft?.terms || {}
  const schedule = terms.installment_schedule
  const index = schedule?.installments?.findIndex(item => item.installment_id === invoice.installment_id) ?? -1
  const installment = index >= 0 ? schedule.installments[index] : null
  const allocation = pkg.review_context
  const policy = terms.withholding_policy
  const structured = Boolean(schedule || policy) || ['vat_amount', 'withholding_amount', 'rounding_adjustment'].some(key => known(invoice[key]))
  const rows = []
  const add = (id, label, expected, actual, contractPaths, invoicePaths, codes = [], note = '') => {
    // Generic policy descriptions are not stored values from a selected contract.
    const showExpected = contract && !(selectedAgreement && ['vat', 'net'].includes(id))
    rows.push({ id, label, expected: showExpected ? expected : expected.map(item => ({ ...item, value: null })), actual, contractPaths, invoicePaths, codes, note })
  }
  for (const key of IDENTITY) add(key, { vendor_id: 'Vendor ID', store_id: 'Store ID', contract_number: 'Contract number' }[key],
    [field('Master identity', contract?.identity?.[key])], [field('Invoice field', invoice[key]), field('Linked identity', pkg.identity[key])], [`/${key}`], [`/${key}`], ['identity_mismatch'])
  add('currency', 'Currency', [field('Approved currency', terms.currency)], [field('Invoice currency', invoice.currency)], ['/currency'], ['/currency'], ['currency_mismatch', 'schedule_currency_mismatch'])
  add('period', 'Service coverage', [field('Effective start', contract?.draft.effective_from), field('Effective end', contract?.draft.effective_to), ...(installment ? [field('Installment start', installment.coverage_start), field('Installment end', installment.coverage_end)] : [])],
    [field('Source start', invoice.service_period_start), field('Source end', invoice.service_period_end), ...(allocation ? [field('Reviewed allocation start', allocation.allocation_start), field('Reviewed allocation end', allocation.allocation_end)] : [])],
    ['/lease_start_date', '/lease_end_date', ...(installment ? [`/installment_schedule/installments/${index}/coverage_start`, `/installment_schedule/installments/${index}/coverage_end`] : [])],
    ['/service_period_start', '/service_period_end'], ['agreement_missing', 'agreement_coverage_missing', 'agreement_version_change', 'installment_coverage_mismatch', 'installment_period_mismatch', 'allocation_period_conflict', 'allocation_source_mismatch', 'approved_installment_allocation'],
    allocation ? 'Reviewed allocation is a human decision. It does not fill missing source invoice dates.' : '')
  add('gross', 'Gross rent', [moneyField(installment ? `Installment ${installment.installment_id}` : schedule ? 'Select an approved installment' : 'Approved fixed rent', schedule ? installment?.gross_amount : terms.fixed_rent, schedule ? schedule.currency : terms.currency), ...(!schedule ? [field('Billing basis', terms.extensions?.fixed_rent_basis)] : [])],
    [moneyField('Gross before taxes', invoice.subtotal, invoice.currency), field('Installment ID', invoice.installment_id)],
    installment ? [`/installment_schedule/installments/${index}/gross_amount`] : schedule ? [] : ['/fixed_rent', '/extensions/fixed_rent_basis'], ['/subtotal', '/installment_id'],
    ['installment_amount_mismatch', 'missing_installment_amount', 'missing_installment_id', 'installment_not_found', 'missing_installment_schedule', 'missing_installment_rule', 'unsupported_installment_pricing', 'unsupported_pricing', 'pricing_basis_unconfigured'],
    installment ? 'Compared with the selected cash installment.' : schedule ? 'An approved installment must be selected before its expected gross amount can be shown.' : 'Fixed rent is shown as stored. The saved server policy determines its billing basis and comparability.')
  add('bank', 'Bank account', [field('Approved account', terms.bank_account)], [field('Invoice account', invoice.bank_account)], ['/bank_account'], ['/bank_account'], ['bank_mismatch', 'bank_reference_missing'])
  add('withholding', 'Withholding', [field('Approved rate (fraction)', policy?.rate), field('Rounding mode', policy?.rounding_mode), field('Decimal places', policy?.decimal_places)],
    [moneyField('Deduction', invoice.withholding_amount, invoice.currency)], ['/withholding_policy'], ['/withholding_amount'],
    ['missing_withholding_rule', 'withholding_amount_mismatch', 'missing_withholding_policy', 'unsupported_withholding_base', 'unsupported_withholding_amount', 'missing_withholding_amount', 'missing_withholding_evidence', 'missing_withholding_evidence_fields', 'withholding_evidence_mismatch', 'duplicate_withholding_evidence', 'missing_withholding_invoice_reference'],
    'Expected deduction is evaluated by the server using the approved rate and rounding policy.')
  add('vat', 'VAT', [field('Requirement', 'Explicit VAT component and applicable supporting tax documents')], [moneyField('VAT addition', invoice.vat_amount, invoice.currency), field('Tax documents', pkg.tax_invoices?.length ?? 0)], [], ['/vat_amount'], ['missing_vat_amount'], 'No VAT rate is inferred from contract text by this view.')
  add('net', 'Net payable', [field('Payment arithmetic', structured ? 'Gross + VAT − withholding + rounding = net payable' : 'Subtotal + signed tax adjustment = total')],
    [moneyField('Net payable', invoice.total, invoice.currency), moneyField('Rounding', invoice.rounding_adjustment, invoice.currency), moneyField('Legacy signed tax', invoice.tax_amount, invoice.currency)], ['/withholding_policy'], ['/total', '/rounding_adjustment', '/tax_amount'],
    ['net_payable_mismatch', 'tax_component_mismatch', 'missing_component_total', 'missing_rounding_policy', 'rounding_adjustment_exceeds_policy', 'unsupported_negative_payable'], 'Arithmetic results are taken from saved findings; this view does not recalculate money.')
  add('conditions', 'Payment conditions', [field('Source payment schedule', terms.payment_schedule), field('Installment conditions', installment?.conditions?.join('\n')), field('Source discrepancy', schedule?.source_discrepancy_note)],
    [field('Reviewer reason', allocation?.reason)], ['/payment_schedule', ...(installment ? [`/installment_schedule/installments/${index}/conditions`, '/installment_schedule/source_discrepancy_note'] : [])], [], ['installment_conditions_review', 'source_pricing_discrepancy'], 'Payment prerequisites require human inspection. Reconciliation does not establish their fulfillment.')
  const sourcePricingDiagnostics = (contract?.draft.extraction_warnings || []).filter(issue => issue?.code === 'source_amount_discrepancy')
  if (sourcePricingDiagnostics.length) {
    add('source_pricing', 'Source pricing review', sourcePricingDiagnostics.map((issue, index) => field(`Retained contract diagnostic${sourcePricingDiagnostics.length > 1 ? ` ${index + 1}` : ''}`, issue.message)),
      [moneyField('Invoice gross before taxes', invoice.subtotal, invoice.currency)], [...new Set(sourcePricingDiagnostics.map(issue => issue.field_path).filter(path => typeof path === 'string' && path.startsWith('/')))], ['/subtotal'], [],
      'Retained contract extraction diagnostic. Inspect source pricing before relying on the amounts; this view preserves the warning without recalculating or resolving it.')
    Object.assign(rows[rows.length - 1], { kind: 'contract_diagnostic', contractDiagnostics: sourcePricingDiagnostics })
  }

  const mapped = new Set()
  const findings = version.assessment.findings || []
  for (const row of rows) {
    row.findings = row.kind === 'contract_diagnostic' ? [] : findings.filter((finding, index) => {
      const owned = !finding.source_document_ids?.length || finding.source_document_ids.includes(pkg.invoice.source_document_id)
      if (!owned) return false
      const path = finding.field_path?.replace(/^\/invoice\/fields/, '').replace(/^\/fields/, '')
      const specificIdentity = finding.code === 'identity_mismatch'
      const matches = row.codes.includes(finding.code) && (!specificIdentity || row.invoicePaths.includes(path))
        || row.invoicePaths.includes(path) && ['missing_field', 'amount_mismatch', 'missing_component_subtotal', 'missing_component_currency'].includes(finding.code)
      if (matches) mapped.add(index)
      return matches
    })
    row.valueComparison = storedValueComparison(row, contract)
    row.status = row.findings.some(item => item.severity === 'blocking') ? 'blocking'
      : row.findings.length ? 'review'
        : selectedAgreement ? 'unavailable' : row.kind === 'contract_diagnostic' ? 'unknown'
        : !agreement ? 'unavailable'
          : !known(row.expected[0]?.value) || !known(row.actual[0]?.value) ? 'unknown' : 'reported'
  }
  return { agreement, selectedAgreement, contract, mode, rows, otherFindings: findings.filter((_, index) => !mapped.has(index)) }
}

/** Resolve only document-qualified field citations, retaining all exact pages and original quotes. */
export function comparisonCitations(sources, paths, evidence, documentIds, qualified = false) {
  const links = []
  for (const documentId of documentIds) {
    const record = sources.find(item => item.documentId === documentId)?.record
    if (!record || record.result?.document?.document_id !== documentId) continue
    const owned = evidence.filter(item => qualified ? item.document_id === documentId : !item.document_id || item.document_id === documentId)
    const pages = new Map()
    for (const path of paths) {
      const resolved = fieldEvidencePages(record, path, owned)
      const quotes = owned.map(item => item.evidence || item).filter(item => item.field_path === path || item.field_path?.startsWith(`${path}/`))
      for (const page of resolved.pages) {
        if (!pages.has(page)) pages.set(page, { documentId, page, record, quotes: [], unresolved: [] })
        const link = pages.get(page)
        link.quotes = [...new Set([...link.quotes, ...quotes])]
        link.unresolved = [...new Set([...link.unresolved, ...resolved.unresolved])]
      }
    }
    links.push(...[...pages.values()].sort((a, b) => a.page - b.page))
  }
  return links
}

/** Load exact historical authority and source PDFs through the host-injected API. No inference or writes. */
export async function loadComparisonResources(api, version) {
  const ref = version.assessment.agreement_reference
  let agreement = null
  let selectedAgreement = null
  let agreementError = ''
  if (hasAssessmentReference(version)) {
    try {
      agreement = comparisonAuthority(version, await api.agreementVersion(ref.agreement_id, ref.version_number))
      if (!agreement) agreementError = 'The returned agreement does not match this assessment’s approved reference.'
    } catch { agreementError = 'The approved agreement version could not be loaded. Retry to inspect its expectations.' }
  } else {
    const selection = confirmedSelection(version)
    if (selection) {
      try {
        selectedAgreement = comparisonSelectedReference(version, await api.agreementVersion(selection.agreement_id, selection.version_number))
        if (!selectedAgreement) agreementError = 'The returned contract does not match this case’s confirmed approved selection. Contract expectations remain unavailable.'
      } catch { agreementError = 'The selected approved contract could not be loaded. Retry to inspect its reference values.' }
    } else agreementError = 'This assessment has no approved agreement reference. Correct the identity or coverage and reassess.'
  }
  const contract = agreement || selectedAgreement
  const ids = [...new Set([version.package.invoice.source_document_id, ...(contract?.draft.source_document_ids || [])].filter(Boolean))]
  const sources = await Promise.all(ids.map(async documentId => {
    try {
      const record = await api.extractionByDocument(documentId)
      if (record?.result?.document?.document_id !== documentId) throw new Error('Source identity mismatch')
      return { documentId, record, error: '' }
    } catch { return { documentId, record: null, error: 'Stored PDF or extraction unavailable. Values and saved findings remain available.' } }
  }))
  return { agreement, selectedAgreement, agreementError, sources }
}
