/** Read-only triage of retained extraction diagnostics. Never establishes semantic approval. */

const normalize = text => typeof text === 'string' ? text.replace(/\s+/gu, ' ').trim() : ''
const hasValue = value => value !== undefined && value !== null && value !== ''

function pointerValue(data, pointer) {
  if (typeof pointer !== 'string' || !pointer.startsWith('/')) return undefined
  let value = data
  for (const token of pointer.slice(1).split('/')) {
    const key = token.replaceAll('~1', '/').replaceAll('~0', '~')
    if (value === null || typeof value !== 'object' || !Object.hasOwn(value, key)) return undefined
    value = value[key]
  }
  return value
}

function sourceIndex(document) {
  const index = new Map()
  for (const page of document?.pages || []) {
    if (!Number.isInteger(page.page_number) || page.page_number < 1) continue
    const sources = [
      ...(page.text_blocks || []).map(block => ({ id: block.block_id, text: block.text })),
      ...(page.images || []).map(image => ({ id: image.asset_id })),
      ...(page.tables || []).map(table => ({ id: table.table_id })),
    ]
    for (const source of sources) {
      if (!source.id) continue
      if (!index.has(source.id)) index.set(source.id, [])
      index.get(source.id).push({ ...source, page: page.page_number })
    }
  }
  return index
}

function citationCheck(document, index, items) {
  if (!document?.document_id) return { citationStatus: 'unavailable', pages: [] }
  if (!items.length) return { citationStatus: 'unverified', pages: [] }
  const pages = new Set()
  let valid = true
  for (const item of items) {
    const evidence = item?.evidence || item
    if (item?.document_id && item.document_id !== document.document_id) { valid = false; continue }
    const ids = evidence?.source_ids || []
    const sources = ids.map(id => index.get(id))
    const exact = ids.length > 0 && sources.every(matches => matches?.length === 1)
    if (exact) sources.forEach(matches => pages.add(matches[0].page))
    const quote = normalize(evidence?.quote)
    if (!exact || !quote || !sources.some(matches => typeof matches?.[0]?.text === 'string' && normalize(matches[0].text).includes(quote))) valid = false
  }
  return { citationStatus: valid ? 'verified' : 'unverified', pages: [...pages].sort((a, b) => a - b) }
}

const EVENTS = {
  source_candidate_diagnostic_retained: 'This retains the raw diagnostic from an earlier automatic candidate whose field index no longer describes the current draft. It does not establish source coverage or correctness. Current narrative and legal-party review and approval requirements remain.',
  field_review_revised: 'An earlier extraction pass revised this candidate. This records a change, not an outstanding extraction failure. Verify the current value and its meaning before approval.',
  party_chain_source_reviewed: 'This records a source-based draft correction. The separate legal-party review requirement remains; this notice is not reviewer approval.',
  prior_terms_retained: 'This records which terms were carried forward rather than rerun. Their ordinary source review and approval are still required.',
}

/** Assess current citation structure separately from semantic review and immutable history.
 * Unknown diagnostics remain active. Rejected-citation diagnostics require exact field support;
 * aggregate semantic review shortcuts also include child citations. Source pages are never inferred
 * from page-like identifiers. Historical status does not certify the value, legal role or completeness.
 */
export function assessWarnings({ record, evidence = [], warnings = [], data = {}, baselineData } = {}) {
  const document = record?.result?.document
  const index = sourceIndex(document)
  const items = warnings.map(issue => {
    const path = issue?.field_path
    const citations = typeof path === 'string' && path.startsWith('/') ? evidence.filter(item => {
      const citedPath = (item?.evidence || item)?.field_path
      return citedPath === path || (issue?.code !== 'invalid_evidence' && typeof citedPath === 'string' && citedPath.startsWith(`${path}/`))
    }) : []
    const check = citationCheck(document, index, citations)
    const value = pointerValue(data, path)
    const changed = baselineData !== undefined && JSON.stringify(value) !== JSON.stringify(pointerValue(baselineData, path))
    let status = 'attention'
    let reason = 'This diagnostic still needs review. No recorded resolution is inferred from a filled value or from viewing this panel.'
    if (Object.hasOwn(EVENTS, issue?.code)) {
      status = 'history'
      reason = EVENTS[issue.code]
    } else if (issue?.code === 'invalid_evidence') {
      if (check.citationStatus === 'verified' && hasValue(value) && typeof value !== 'object' && !changed) {
        status = 'history'
        reason = 'Earlier candidate citation(s) were rejected. All current citations for this exact field are traceable in the attached source text. This checks citation structure only; semantic correctness and complete conditions still require review.'
      } else if (changed) {
        reason = 'This value was edited after the saved draft or extraction. Earlier citations do not verify the edited value; inspect the complete source again.'
      } else {
        reason = 'Current evidence could not be fully verified for this field: check the attached original, exact source references, literal quote and current value. This retained diagnostic stays in Needs review.'
      }
    } else if (issue?.code === 'source_text_review_required') {
      reason = 'Current human review is required for this narrative, including conditions and exceptions. A literal quotation does not prove the extracted meaning or completeness.'
    } else if (issue?.code === 'party_roles_review_required') {
      reason = 'An authorized reviewer must confirm the landlord, tenant and complete representation chains. Corrected names and traceable quotations do not replace that decision.'
    } else if (issue?.code === 'field_review_incomplete') {
      reason = hasValue(value)
        ? 'A value is now present, but the earlier focused review did not resolve this field. Confirm its source or external master assignment; presence alone does not resolve the review.'
        : 'The extraction did not resolve this field. Confirm whether a value is required or is genuinely not applicable; an empty optional field is not automatically an error.'
    }
    return { issue, status, reason, ...check }
  })
  const attention = items.filter(item => item.status === 'attention')
  const history = items.filter(item => item.status === 'history')
  return { items, attention, history, counts: { attention: attention.length, history: history.length, total: items.length } }
}
