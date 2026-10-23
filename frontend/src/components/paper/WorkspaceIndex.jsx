import { useCallback, useEffect, useId, useMemo, useRef, useState } from 'react'
import { ArrowRight, FileCheck2, Files, Link2, RefreshCw, Search } from 'lucide-react'
import { formatError } from '../../paper/helpers.js'
import { createWorkspaceRequestGate, documentWorkflowActions, nextActionLabel, workspaceQuery, workspaceStatus } from '../../paper/workspaceNavigation.js'
import './workspaceIndex.css'

const MODES = {
  cases: {
    title: 'Invoice cases',
    description: 'Follow each invoice from its confirmed contract through review and reconciliation.',
    search: 'Invoice, contract, supplier or location',
    method: 'workspaceCases',
    statuses: ['incomplete', 'mismatched', 'needs_review', 'matched', 'approved', 'rejected', 'duplicate'],
    empty: 'No invoice cases found. Review an invoice from the document inbox and confirm its contract to create a case.',
  },
  contracts: {
    title: 'Contracts and their invoices',
    description: 'Open a contract to inspect its terms, approval history and explicitly linked invoice cases.',
    search: 'Contract, supplier or location',
    method: 'workspaceContracts',
    statuses: ['draft', 'approved'],
    empty: 'No contracts found. Review an agreement from the document inbox, then save its draft to the agreement master.',
  },
  documents: {
    title: 'Document inbox',
    description: 'See extraction progress, review original PDFs and continue into the exact saved workflow version.',
    search: 'PDF filename',
    method: 'workspaceDocuments',
    statuses: ['processing', 'extraction_failed', 'ready_for_review', 'agreement_draft', 'agreement_approved', 'invoice_case'],
    empty: 'No documents found. Upload an agreement or invoice PDF to begin.',
  },
}

const dateLabel = value => {
  const date = value && new Date(value)
  return date && !Number.isNaN(date.getTime()) ? date.toLocaleDateString() : null
}

function Status({ value }) {
  const tone = ['approved', 'matched', 'agreement_approved'].includes(value) ? 'positive' : ['failed', 'extraction_failed', 'mismatched', 'rejected', 'duplicate'].includes(value) ? 'negative' : ['incomplete', 'needs_review', 'draft', 'agreement_draft', 'ready_for_review'].includes(value) ? 'attention' : 'neutral'
  return <span className={`paper-workspace-status paper-workspace-status--${tone}`}>{workspaceStatus(value)}</span>
}

/** Source links are navigation references; choosing one never changes saved association or authority. */
export function DocumentWorkflowActions({ document, onAction }) {
  const { links, total, primary, needsChoice, truncated } = documentWorkflowActions(document)
  if (!total) return null
  const targetButton = link => <button key={`${link.kind}:${link.id}:${link.version_number}`} type="button" className="paper-source-link" disabled={!onAction} onClick={() => onAction?.(document, link)}>
    {link.kind === 'agreement' ? 'Agreement' : 'Invoice case'}{link.label ? ` ${link.label}` : ''} v{link.version_number} · {workspaceStatus(link.status)}{!link.is_latest ? ' · Historical version' : ''}<ArrowRight size={12} aria-hidden="true" />
  </button>
  return <div className="paper-workspace-document-links">
    {document.workflow_status && <p className="paper-workspace-caption">{workspaceStatus(document.workflow_status)}</p>}
    {primary ? <div><span className="paper-workspace-caption">Saved workflow</span>{targetButton(primary)}</div> : needsChoice && <details>
      <summary>{total} saved version links · choose a version</summary>
      <p>These saved versions use this source. Choose the exact version to continue reviewing.</p>
      <div className="paper-workspace-link-options">{links.map(targetButton)}</div>
      {truncated && <p>Showing {links.length} of {total} links. Open a saved agreement or case to browse its full version history.</p>}
    </details>}
  </div>
}

function CaseCard({ item, onOpen }) {
  const association = item.association
  return <article className="paper-workspace-card">
    <header><div><p className="paper-workspace-eyebrow">Invoice case · v{item.version_number}</p><h3>{item.invoice_number || 'Invoice number not recorded'}</h3></div><Status value={item.status} /></header>
    <p className="paper-workspace-party">{item.vendor_name || 'Supplier not recorded'}</p>
    {item.location && <p className="paper-workspace-location">{item.location}</p>}
    <div className="paper-workspace-contract"><Link2 size={14} aria-hidden="true" /><span>Contract {item.identity?.contract_number || 'not assigned'}{association?.version_number ? ` · v${association.version_number}` : ''}<small>{association?.kind === 'confirmed' ? 'Reviewer-confirmed association' : association?.kind === 'legacy_identity' ? 'Legacy identity reference · confirmation required' : 'No saved contract association'}</small></span></div>
    <footer><p>{item.blocking_count > 0 ? `${item.blocking_count} blocking ${item.blocking_count === 1 ? 'issue' : 'issues'}` : 'No blocking issues'}{item.review_count > 0 ? ` · ${item.review_count} to review` : ''}</p><button type="button" className="paper-primary" disabled={!onOpen} onClick={() => onOpen?.(item)}>{nextActionLabel(item.next_action)}<ArrowRight size={14} aria-hidden="true" /></button></footer>
  </article>
}

function ContractCard({ item, onOpen, onViewInvoices }) {
  return <article className="paper-workspace-card">
    <header><div><p className="paper-workspace-eyebrow">Agreement master · v{item.version_number}</p><h3>Contract {item.identity?.contract_number || 'number not recorded'}</h3></div><Status value={item.status} /></header>
    <p className="paper-workspace-party">{item.vendor_name || 'Supplier not recorded'}</p>
    {item.location && <p className="paper-workspace-location">{item.location}</p>}
    <div className="paper-workspace-contract"><FileCheck2 size={14} aria-hidden="true" /><span>{item.linked_case_count} confirmed invoice {item.linked_case_count === 1 ? 'case' : 'cases'}<small>{item.approved_version_number ? `Approved version: v${item.approved_version_number}` : 'No approved version yet'}{item.legacy_case_count > 0 ? ` · ${item.legacy_case_count} legacy identity ${item.legacy_case_count === 1 ? 'reference' : 'references'}` : ''}</small></span></div>
    <footer><div className="flex flex-wrap gap-2">{onViewInvoices && <button type="button" className="paper-secondary" onClick={() => onViewInvoices(item)}>Linked invoices ({item.linked_case_count})</button>}</div><button type="button" className="paper-primary" disabled={!onOpen} onClick={() => onOpen?.(item)}>Review contract<ArrowRight size={14} aria-hidden="true" /></button></footer>
  </article>
}

function DocumentCard({ item, onOpen, onAction }) {
  const hasSavedLinks = item.workflow_links_total > 0 || item.workflow_links?.length > 0
  const linksUnavailable = item.workflow_links_resolved === false && item.status === 'completed'
  return <article className="paper-workspace-card">
    <header><div><p className="paper-workspace-eyebrow">{item.schema_name === 'rent_agreement' ? 'Agreement PDF' : 'Invoice PDF'}{item.archived ? ' · Archived attempt' : ''}</p><h3>{item.filename}</h3></div>{linksUnavailable ? <span className="paper-workspace-status paper-workspace-status--attention">Saved links unavailable</span> : <Status value={item.workflow_status} />}</header>
    <div className="paper-workspace-document-meta"><span>Extraction: {workspaceStatus(item.status)}</span><span>{dateLabel(item.created_at)}</span>{item.warning_count > 0 && <span>{item.warning_count} retained log {item.warning_count === 1 ? 'entry' : 'entries'}</span>}</div>
    {hasSavedLinks ? <DocumentWorkflowActions document={item} onAction={onAction} /> : <p className="paper-workspace-caption">{linksUnavailable ? 'This older upload’s source index needs repair. Check Cases or Contracts for existing saved work before preparing another draft.' : item.workflow_status === 'ready_for_review' ? 'Extraction is ready. Review the fields and source, then save a draft.' : item.workflow_status === 'extraction_failed' ? 'Open the attempt to inspect the error and retry extraction.' : 'The extraction result will appear when processing finishes.'}</p>}
    <footer><span className="paper-workspace-caption">{linksUnavailable ? 'Saved workflow links have not been established.' : hasSavedLinks ? 'Existing saved versions remain available.' : 'No saved workflow version yet.'}</span><button type="button" className="paper-secondary" disabled={!onOpen} onClick={() => onOpen?.(item)}><Files size={14} aria-hidden="true" />{hasSavedLinks || linksUnavailable ? 'Review original' : nextActionLabel(item.next_action)}<ArrowRight size={14} aria-hidden="true" /></button></footer>
  </article>
}

/** Render safe stored summaries; no displayed text can assign a contract or change a workflow. */
export function WorkspaceIndexItems({ items = [], mode = 'cases', onOpenCase, onOpenContract, onViewInvoices, onOpenDocument, onDocumentAction }) {
  return <div className="paper-workspace-grid">{items.map(item => mode === 'cases' ? <CaseCard key={item.case_id} item={item} onOpen={onOpenCase} /> : mode === 'contracts' ? <ContractCard key={item.agreement_id} item={item} onOpen={onOpenContract} onViewInvoices={onViewInvoices} /> : <DocumentCard key={item.job_id} item={item} onOpen={onOpenDocument} onAction={onDocumentAction} />)}</div>
}

/** Searchable, bounded read-only index; selected editors and unsaved state remain owned by the parent. */
export default function WorkspaceIndex({ api, mode = 'cases', active = true, refreshKey, agreementFilter, onClearAgreementFilter, onOpenCase, onOpenContract, onViewInvoices, onOpenDocument, onDocumentAction }) {
  const spec = MODES[mode] || MODES.cases
  const id = useId()
  const [search, setSearch] = useState('')
  const [filters, setFilters] = useState({ q: '', status: '', archived: false, offset: 0 })
  const [page, setPage] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)
  const gate = useRef(createWorkspaceRequestGate())
  const agreementId = agreementFilter?.agreement_id
  const associationKind = agreementFilter?.association_kind || 'confirmed'
  const [previousContext, setPreviousContext] = useState(`${mode}:${agreementId || ''}:${associationKind}`)
  const currentContext = `${mode}:${agreementId || ''}:${associationKind}`
  if (previousContext !== currentContext) {
    gate.current.invalidate()
    setPreviousContext(currentContext)
    setSearch('')
    setFilters({ q: '', status: '', archived: false, offset: 0 })
    setPage(null)
  }
  const query = useMemo(() => workspaceQuery({ mode, ...filters, agreementFilter: agreementId ? { agreement_id: agreementId, association_kind: associationKind } : null }), [mode, filters, agreementId, associationKind])
  const load = useCallback(async () => {
    const request = gate.current.start()
    setLoading(true)
    setError('')
    try {
      const result = await api[spec.method](query)
      if (gate.current.isCurrent(request)) setPage(result)
    } catch (err) {
      if (gate.current.isCurrent(request)) setError(formatError(err))
    } finally {
      if (gate.current.isCurrent(request)) setLoading(false)
    }
  }, [api, spec.method, query])
  useEffect(() => {
    load()
    const requestGate = gate.current
    return () => { requestGate.invalidate() }
  }, [load, refreshKey, retry])
  const processing = mode === 'documents' && page?.items?.some(item => ['pending', 'processing'].includes(item.status))
  useEffect(() => {
    if (!active || !processing || loading || error) return undefined
    const timer = window.setTimeout(() => setRetry(value => value + 1), 4000)
    return () => window.clearTimeout(timer)
  }, [active, processing, loading, error])
  const changeFilter = patch => { gate.current.invalidate(); setFilters(current => ({ ...current, ...patch, offset: 0 })); setPage(null) }
  const changePage = offset => { gate.current.invalidate(); setFilters(current => ({ ...current, offset })); setPage(null) }
  const items = page?.items || []
  return <section className="paper-panel paper-workspace-index" aria-labelledby={`${id}-title`} aria-busy={loading}>
    <div className="paper-workspace-heading"><div><h2 id={`${id}-title`}>{spec.title}</h2><p>{spec.description}</p></div><button type="button" className="paper-secondary" disabled={loading} onClick={() => setRetry(value => value + 1)} aria-label={`Refresh ${spec.title.toLowerCase()}`}><RefreshCw size={14} aria-hidden="true" />Refresh</button></div>
    {mode === 'cases' && agreementId && <div className="paper-workspace-filter-note"><Link2 size={14} aria-hidden="true" /><span>{associationKind === 'legacy_identity' ? 'Legacy identity references' : 'Confirmed invoice cases'} for contract {agreementFilter.contract_number || agreementId}</span>{onClearAgreementFilter && <button type="button" className="paper-source-link" onClick={onClearAgreementFilter}>Show all cases</button>}</div>}
    <form className="paper-workspace-filters" onSubmit={event => { event.preventDefault(); changeFilter({ q: search }) }}>
      <label className="paper-workspace-search" htmlFor={`${id}-search`}><span>Search {mode === 'cases' ? 'invoice cases' : mode}</span><div><Search size={15} aria-hidden="true" /><input id={`${id}-search`} type="search" maxLength={200} placeholder={spec.search} value={search} onChange={event => setSearch(event.target.value)} /><button type="submit" className="paper-secondary">Search</button></div></label>
      <label htmlFor={`${id}-status`}><span>Status</span><select id={`${id}-status`} value={filters.status} onChange={event => changeFilter({ status: event.target.value })}><option value="">All statuses</option>{spec.statuses.map(status => <option key={status} value={status}>{workspaceStatus(status)}</option>)}</select></label>
      {mode === 'documents' && <label className="paper-workspace-archive"><input type="checkbox" checked={filters.archived} onChange={event => changeFilter({ archived: event.target.checked })} /><span>Archived extraction attempts</span></label>}
    </form>
    {error && <div className="paper-workspace-error" role="alert"><p>{error}</p>{page && <p>The last loaded results are shown. Refresh to check for changes.</p>}<button type="button" className="paper-source-link" disabled={loading} onClick={() => setRetry(value => value + 1)}>Try again</button></div>}
    {loading && <p className="paper-workspace-caption" role="status">{page ? 'Refreshing results…' : 'Loading results…'}</p>}
    {!loading && page && !items.length && <p className="paper-workspace-empty">{spec.empty}</p>}
    <WorkspaceIndexItems items={items} mode={mode} onOpenCase={onOpenCase} onOpenContract={onOpenContract} onViewInvoices={onViewInvoices} onOpenDocument={onOpenDocument} onDocumentAction={onDocumentAction} />
    {page && <nav className="paper-workspace-pagination" aria-label={`${spec.title} pages`}><button type="button" className="paper-secondary" disabled={loading || !page.offset} onClick={() => changePage(Math.max(0, page.offset - page.limit))}>Previous</button><p>{page.total ? `${page.offset + 1}–${Math.min(page.offset + page.limit, page.total)} of ${page.total}` : '0 results'}</p><button type="button" className="paper-secondary" disabled={loading || page.offset + page.limit >= page.total} onClick={() => changePage(page.offset + page.limit)}>Next</button></nav>}
  </section>
}
