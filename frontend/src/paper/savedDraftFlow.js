import { draftReference } from './draftSelection.js'

const copy = value => JSON.parse(JSON.stringify(value))

/** Discard readiness from an earlier policy before enabling reconciliation. */
export function readinessForPolicy(readiness, context) {
  if (!context?.policy_id || !context?.policy_version) return null
  return readiness?.policy_id === context.policy_id && readiness.policy_version === context.policy_version ? readiness : null
}
const ROLES = new Set(['rent_invoice', 'tax_invoice', 'utility_statement', 'supporting_document'])
const SUPPORT_KEYS = ['tax_invoices', 'utility_statements', 'supporting_documents']
const text = (value, label) => {
  if (typeof value !== 'string' || !value.trim()) throw new Error(`${label} is required.`)
  return value.trim()
}
const version = value => {
  if (!Number.isSafeInteger(value) || value < 1) throw new Error('A positive saved version is required.')
  return value
}
const date = (value, label) => {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) throw new Error(`${label} must be a valid date.`)
  const parsed = new Date(`${value}T00:00:00Z`)
  if (Number.isNaN(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== value) throw new Error(`${label} must be a valid date.`)
  return value
}

function allocationRequest(context) {
  const allocation_start = date(context.allocation_start, 'Allocation start')
  const allocation_end = date(context.allocation_end, 'Allocation end')
  if (allocation_end < allocation_start) throw new Error('Allocation end must not precede its start.')
  if (!Array.isArray(context.source_document_ids) || !context.source_document_ids.length || context.source_document_ids.length > 100) throw new Error('Allocation requires between 1 and 100 source document IDs.')
  const source_document_ids = context.source_document_ids.map(value => text(value, 'Allocation source document ID'))
  if (new Set(source_document_ids).size !== source_document_ids.length) throw new Error('Allocation source document IDs must be unique.')
  return { allocation_start, allocation_end, reason: text(context.reason, 'Allocation reason'), source_document_ids }
}

/** Build explicit comparison intent; the server resolves fields and reviewer provenance. */
export function preparationRequest({ selection, package: pkg, caseId = null, expectedVersion = null }) {
  if (!selection?.invoice) throw new Error('Choose a reviewed saved invoice before preparing a case.')
  if (!pkg?.association) throw new Error('Confirm the invoice contract before checking readiness.')
  const identity = { vendor_id: text(pkg.identity?.vendor_id, 'Vendor ID'), store_id: text(pkg.identity?.store_id, 'Store ID'), contract_number: text(pkg.identity?.contract_number, 'Contract number') }
  const request = { identity, invoice: draftReference(selection.invoice) }
  const refs = [request.invoice]
  for (const key of SUPPORT_KEYS) {
    const values = selection[key] ?? []
    if (!Array.isArray(values)) throw new Error('Selected document references must be a list.')
    request[key] = values.map(draftReference)
    refs.push(...request[key])
  }
  if (refs.length > 100) throw new Error('Select no more than 100 documents in one case.')
  if (new Set(refs.map(ref => ref.draft_id)).size !== refs.length) throw new Error('Select only one version of each document draft.')
  request.association = { agreement_id: text(pkg.association.agreement_id, 'Associated agreement'), version_number: version(pkg.association.version_number), reason: text(pkg.association.reason, 'Contract association reason') }
  if (pkg.review_context != null) request.review_context = allocationRequest(pkg.review_context)
  if ((caseId != null) !== (expectedVersion != null)) throw new Error('A case revision requires both its case ID and expected version.')
  if (caseId != null) {
    request.case_id = text(caseId, 'Case ID')
    request.expected_version = version(expectedVersion)
  }
  return request
}

/** Save document review without importing package, matching or approval state. */
export function draftSaveRequest(record, role, document, reviewed, reason) {
  if (!ROLES.has(role) || (record?.role && record.role !== role)) throw new Error('The saved draft role cannot change.')
  if (typeof reviewed !== 'boolean') throw new Error('Document review intent must be an explicit boolean.')
  if (!document || typeof document !== 'object' || Array.isArray(document)) throw new Error('Document source values are required.')
  text(document.source_document_id, 'Source document ID')
  const request = { role, document: copy(document), reviewed, reason: text(reason, 'Save reason') }
  if (record != null) request.expected_version = version(record.version_number)
  return request
}
