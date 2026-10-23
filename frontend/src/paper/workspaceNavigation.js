const ACTION_LABELS = {
  view_case: 'Open case',
  review_duplicate: 'Review duplicate',
  review_and_decide: 'Review and decide',
  resolve_discrepancies: 'Review discrepancies',
  review_agreement: 'Review agreement',
  view_invoices: 'View contract and invoices',
  wait_for_extraction: 'View extraction progress',
  retry_extraction: 'Review failed extraction',
  review_invoice: 'Review invoice',
  open_agreement: 'Open saved agreement',
  open_case: 'Open saved case',
}

/** Build the bounded read query; contract filtering uses saved associations explicitly. */
export function workspaceQuery({ mode, q = '', status = '', offset = 0, archived = false, agreementFilter }) {
  const query = { q: q.trim(), ...(status ? { status } : {}), limit: 20, offset }
  if (mode === 'documents') {
    delete query.status
    if (status) query.workflow_status = status
    query.archived = archived
  }
  if (mode === 'cases' && agreementFilter?.agreement_id) {
    query.agreement_id = agreementFilter.agreement_id
    query.association_kind = agreementFilter.association_kind || 'confirmed'
  }
  return query
}

/** Label a proposed next step without implying a reconciliation or approval outcome. */
export function nextActionLabel(action) {
  return ACTION_LABELS[action] || 'Open workspace'
}

/** Show stored workflow status in plain language. */
export function workspaceStatus(status) {
  if (!status) return 'Unknown status'
  const text = String(status).replaceAll('_', ' ')
  return text.charAt(0).toUpperCase() + text.slice(1)
}

/** Retain exact saved targets and require a choice whenever the source has multiple links. */
export function documentWorkflowActions(document) {
  const links = document?.workflow_links || []
  const total = Math.max(document?.workflow_links_total || 0, links.length)
  return { links, total, primary: total === 1 && links.length === 1 ? links[0] : null, needsChoice: total > 1, truncated: total > links.length }
}

/** Guard asynchronous list refreshes against changed filters and disposed workspace scopes. */
export function createWorkspaceRequestGate() {
  let revision = 0
  return {
    start: () => ++revision,
    isCurrent: request => request === revision,
    invalidate: () => { revision += 1 },
  }
}
