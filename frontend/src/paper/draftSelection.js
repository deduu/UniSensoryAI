const SUPPORTING_ROLES = { tax_invoice: 'tax_invoices', utility_statement: 'utility_statements', supporting_document: 'supporting_documents' }
const ROLE_KEYS = { rent_invoice: 'invoice', ...SUPPORTING_ROLES }
const copy = value => JSON.parse(JSON.stringify(value))
const keyOf = ref => `${ref.draft_id}:${ref.version_number}`
const sameRef = (a, b) => a?.draft_id === b?.draft_id && a?.version_number === b?.version_number

/** Return a validated immutable reference to one saved document version. */
export function draftReference(record) {
  if (typeof record?.draft_id !== 'string' || !record.draft_id.trim() || !Number.isSafeInteger(record.version_number) || record.version_number < 1) throw new Error('A saved draft ID and positive version are required.')
  return { draft_id: record.draft_id, version_number: record.version_number }
}

function entries(selection) {
  if (!selection?.invoice) throw new Error('Choose a reviewed invoice before preparing a case.')
  const rows = [{ role: 'rent_invoice', ref: draftReference(selection.invoice) }]
  for (const [role, key] of Object.entries(SUPPORTING_ROLES)) {
    const values = selection[key] ?? []
    if (!Array.isArray(values)) throw new Error('Selected supporting document references must be a list.')
    for (const ref of values) rows.push({ role, ref: draftReference(ref) })
  }
  if (rows.length > 100) throw new Error('Select no more than 100 documents in one case, including its invoice.')
  if (new Set(rows.map(row => keyOf(row.ref))).size !== rows.length) throw new Error('This draft version is already selected.')
  if (new Set(rows.map(row => row.ref.draft_id)).size !== rows.length) throw new Error('Select only one version of each document draft.')
  return rows
}

function validateRecord(record, role, ref) {
  if (!sameRef(record, ref)) throw new Error('The document service did not return the requested version.')
  if (record.role !== role) throw new Error('The saved document role does not match this selection.')
  if (record.status !== 'reviewed') throw new Error('Only reviewed document versions can be selected for reconciliation.')
  if (typeof record.document?.source_document_id !== 'string' || !record.document.source_document_id.trim()) throw new Error('A canonical source document ID is required.')
}

function selectedRecords(selection, records) {
  const byRef = new Map(records.map(record => [keyOf(record), record]))
  const rows = entries(selection).map(({ role, ref }) => {
    const record = byRef.get(keyOf(ref))
    if (!record) throw new Error('A selected saved document version has not been loaded. Retry selection.')
    validateRecord(record, role, ref)
    return record
  })
  if (new Set(rows.map(record => record.document.source_document_id)).size !== rows.length) throw new Error('The same source document cannot be selected more than once.')
  return rows
}

/** Add one reviewed supporting draft without mutating the existing selection. */
export function addReviewedDraft(selection, record, records = []) {
  const roleKey = SUPPORTING_ROLES[record?.role]
  if (!roleKey) throw new Error('Choose the primary reviewed invoice from the saved draft library.')
  const ref = draftReference(record)
  const next = { ...copy(selection), [roleKey]: [...(selection[roleKey] || []), ref] }
  selectedRecords(next, [...records, record])
  return next
}

/** Remove an exact supporting version while retaining the fixed invoice. */
export function removeSelectedDraft(selection, role, ref) {
  const roleKey = SUPPORTING_ROLES[role]
  if (!roleKey) throw new Error('Change the primary invoice from the saved draft library.')
  return { ...copy(selection), [roleKey]: (selection[roleKey] || []).filter(item => !sameRef(item, ref)) }
}

/** Load and validate every exact selection; never fall back to latest revisions. */
export async function hydrateDraftSelection(api, selection) {
  const rows = entries(selection)
  const records = await Promise.all(rows.map(async ({ role, ref }) => {
    const record = await api.documentDraftVersion(ref.draft_id, ref.version_number)
    validateRecord(record, role, ref)
    return record
  }))
  return selectedRecords(selection, records)
}

/** Preserve package metadata and complete source documents without interpreting values. */
export function packageFromDraftSelection(pkg, selection, records) {
  const validated = selectedRecords(selection, records)
  const next = { ...copy(pkg || {}), invoice: null, tax_invoices: [], utility_statements: [], supporting_documents: [] }
  for (const record of validated) {
    const key = ROLE_KEYS[record.role]
    if (key === 'invoice') next.invoice = copy(record.document)
    else next[key].push(copy(record.document))
  }
  return next
}

export const documentRoleLabel = role => ({ rent_invoice: 'Rent invoice', tax_invoice: 'Tax invoice', utility_statement: 'Utility statement', supporting_document: 'Supporting document' })[role] || 'Document'

export const documentDraftLabel = record => record?.document?.fields?.invoice_number || record?.document?.fields?.reference_number || record?.document?.fields?.document_number || documentRoleLabel(record?.role)
