import { reviewFieldValue } from './sourceReview.js'

const EXTERNAL_IDENTIFIERS = new Set(['/vendor_id', '/store_id'])
const missing = value => value === undefined || value === null || value === ''
const words = text => text.replaceAll('_', ' ').replace(/^./, letter => letter.toUpperCase())

function fieldLabel(path) {
  return path ? path.slice(1).split('/').map(token => {
    const key = token.replaceAll('~1', '/').replaceAll('~0', '~')
    return /^\d+$/.test(key) ? `Item ${Number(key) + 1}` : words(key) || 'Unnamed field'
  }).join(' · ') : 'Document review'
}

function summaryFor(item, fieldPath, valueState) {
  if (item.status === 'history') return {
    type: 'Extraction history',
    why: 'Earlier extraction activity is retained.',
    nextAction: 'Read Details; this does not confirm current data.',
  }
  const code = item.issue?.code
  if (code === 'field_review_incomplete') {
    if (EXTERNAL_IDENTIFIERS.has(fieldPath)) return {
      type: valueState === 'missing' ? 'Source ID not extracted' : 'Source ID unconfirmed',
      why: valueState === 'missing' ? 'Source ID not extracted; master assignment is separate.' : 'Extracted ID remains unconfirmed.',
      nextAction: valueState === 'missing' ? 'Verify the assigned master ID.' : 'Check source and assigned master ID separately.',
    }
    return {
      type: valueState === 'missing' || valueState === 'empty' ? 'Value unresolved' : 'Value unconfirmed',
      why: valueState === 'missing' || valueState === 'empty' ? 'Extraction did not establish a value.' : 'Present value remains unconfirmed.',
      nextAction: valueState === 'missing' || valueState === 'empty' ? 'Confirm whether needed; enter source value or leave unknown.' : 'Compare with source or assigned master.',
    }
  }
  if (code === 'invalid_evidence') return {
    type: 'Source check', why: 'Citation does not fully verify this value.',
    nextAction: 'Compare value and complete source passage.',
  }
  if (code === 'source_text_review_required') return {
    type: 'Clause review', why: 'Clause completeness and meaning need review.',
    nextAction: 'Check conditions and exceptions in the original.',
  }
  if (code === 'party_roles_review_required') return {
    type: 'Party review', why: 'Party roles and authority need confirmation.',
    nextAction: 'Verify landlord, tenant and complete representation chains.',
  }
  if (code === 'source_amount_discrepancy') return {
    type: 'Amounts differ', why: 'Printed amounts disagree.',
    nextAction: 'Compare rent, total and installments; record the difference.',
  }
  if (code === 'installment_schedule_source_unresolved') return {
    type: 'Allocation needed', why: 'Installment allocations are incomplete.',
    nextAction: 'Review payment clauses; assign IDs and coverage.',
  }
  if (typeof code === 'string' && code.startsWith('source_text_')) return {
    type: 'Clause source check', why: 'Clause source selection needs review.',
    nextAction: 'Compare the original clause and draft; read Details.',
  }
  return {
    type: 'Review diagnostic', why: 'A diagnostic has no recorded resolution.',
    nextAction: 'Read Details and check the source.',
  }
}

/** Group assessed diagnostics for reading without changing status, values or retained entries. */
export function groupReviewIssues(items = [], data = {}) {
  const groups = new Map()
  for (const item of items) {
    const rawPath = item?.issue?.field_path
    const fieldPath = typeof rawPath === 'string' && rawPath.startsWith('/') ? rawPath : ''
    const key = fieldPath || 'document'
    if (!groups.has(key)) {
      const value = reviewFieldValue(data, fieldPath)
      groups.set(key, {
        key, fieldPath, label: fieldLabel(fieldPath), value,
        valueState: missing(value) ? 'missing' : typeof value === 'object' && Object.keys(value).length === 0 ? 'empty' : 'present',
        status: item?.status === 'history' ? 'history' : 'attention', issueCount: 0, summaries: [], pages: [], items: [],
      })
    }
    const group = groups.get(key)
    const status = item?.status === 'history' ? 'history' : 'attention'
    if (group.status !== status) group.status = 'mixed'
    group.items.push(item)
    group.issueCount += 1
    group.pages = [...new Set([...group.pages, ...(item?.pages || []).filter(page => Number.isInteger(page) && page > 0)])].sort((a, b) => a - b)
    const summary = summaryFor(item, fieldPath, group.valueState)
    const existing = group.summaries.find(entry => entry.type === summary.type && entry.why === summary.why && entry.nextAction === summary.nextAction)
    if (existing) existing.count += 1
    else group.summaries.push({ ...summary, count: 1 })
  }
  return [...groups.values()]
}
