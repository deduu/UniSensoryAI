import { useEffect, useId, useRef, useState } from 'react'
import { AlertTriangle, ArrowUpLeft, Files, MessageSquareQuote, Search, X } from 'lucide-react'
import { pageCount, projectReviewItems } from '../../paper/sourceReview'

const INITIAL_STATE = { panel: '', fieldPath: '', label: '', fieldEvidence: null }

/** Persistent, non-modal access to exact evidence, retained warnings and source references. */
export default function ReviewInspector({ record, evidence = [], warnings = [], sourceDocumentIds = [], pageNumber, state, onChange, onNavigate, onReturnToField }) {
  const [localState, setLocalState] = useState(INITIAL_STATE)
  const [query, setQuery] = useState('')
  const [pageOnly, setPageOnly] = useState(false)
  const panelState = state ?? localState
  const change = onChange ?? setLocalState
  const heading = useRef(null)
  const trigger = useRef(null)
  const toolbar = useRef(null)
  const panelId = useId()
  const collection = panelState.fieldEvidence ?? evidence
  const filtered = projectReviewItems(record, { evidence: collection, warnings, fieldPath: panelState.fieldPath, pageNumber: pageOnly ? pageNumber : null, query })
  const sourceIds = [...new Set([...(record?.result?.document?.document_id ? [record.result.document.document_id] : []), ...sourceDocumentIds])]
  const tabs = [
    { id: 'evidence', label: 'Evidence', count: evidence.length, icon: MessageSquareQuote },
    { id: 'warnings', label: 'Warnings', count: warnings.length, icon: AlertTriangle },
    { id: 'sources', label: 'Sources', count: sourceIds.length, icon: Files },
  ]
  const activeTab = tabs.find(tab => tab.id === panelState.panel)

  useEffect(() => {
    if (panelState.panel) heading.current?.focus({ preventScroll: true })
    setQuery('')
    setPageOnly(false)
  }, [panelState.panel, panelState.fieldPath, record?.job_id])

  function close() {
    change({ ...panelState, panel: '' })
    const target = trigger.current?.isConnected ? trigger.current : toolbar.current?.querySelector('button')
    target?.focus({ preventScroll: true })
  }

  function open(event, panel) {
    trigger.current = event.currentTarget
    change({ ...INITIAL_STATE, panel: panelState.panel === panel && !panelState.fieldPath ? '' : panel })
  }

  return <aside className="paper-review-dock" aria-label="Review tools" data-review-panel={panelState.panel || 'closed'} onKeyDown={event => { if (event.key === 'Escape' && panelState.panel) { event.stopPropagation(); close() } }}>
    {activeTab && <section id={panelId} className="paper-review-inspector" aria-label={`${activeTab.label} inspector`}>
      <header className="flex min-w-0 items-start justify-between gap-2 border-b border-surface-border p-3">
        <div className="min-w-0"><h3 ref={heading} tabIndex={-1} className="text-sm font-semibold focus:outline-none">{activeTab.label === 'Evidence' ? 'Field evidence' : activeTab.label === 'Sources' ? 'Source review' : 'Extraction warnings'}</h3><p className="mt-1 break-words text-xs text-ink-muted">{panelState.fieldPath ? `For ${panelState.label || panelState.fieldPath}` : record?.filename || 'Saved document review'}</p></div>
        <button type="button" aria-label="Close review inspector" className="paper-secondary !p-1.5" onClick={close}><X size={15} /></button>
      </header>
      {panelState.panel !== 'sources' && <div className="paper-review-inspector-filters space-y-2 border-b border-surface-border p-3">
        {panelState.fieldPath && <div className="flex flex-wrap items-center justify-between gap-2"><button type="button" className="paper-text-action text-xs" onClick={() => change({ ...panelState, fieldPath: '', label: '', fieldEvidence: null })}>Show all {panelState.panel}</button>{onReturnToField && <button type="button" className="paper-text-action text-xs" onClick={onReturnToField}><ArrowUpLeft size={13} /> Back to field</button>}</div>}
        <label className="relative block"><Search aria-hidden="true" size={14} className="pointer-events-none absolute left-2.5 top-2.5 text-ink-faint" /><input aria-label={`Search ${activeTab.label.toLowerCase()}`} type="search" className="paper-input !py-2 !pl-8 !text-xs" placeholder={panelState.panel === 'evidence' ? 'Find a field or quoted text' : 'Find a warning or field'} value={query} onChange={event => setQuery(event.target.value)} /></label>
        {record && Number.isInteger(pageNumber) && <label className="flex items-center gap-2 text-xs text-ink-muted"><input type="checkbox" className="rounded text-brand" checked={pageOnly} onChange={event => setPageOnly(event.target.checked)} /> Current PDF page only ({pageNumber})</label>}
      </div>}
      <div className="paper-review-inspector-body" key={panelState.panel}>
        {panelState.panel === 'evidence' && <>
          <p className="mb-3 text-xs text-ink-muted">{filtered.evidence.length} citation(s). Check the quote and complete conditions; a citation does not confirm an edited value.</p>
          <div className="space-y-3">{filtered.evidence.map(({ item, pages, unresolved }, index) => {
            const quote = item.evidence || item
            return <article key={index} className="min-w-0 rounded-lg border border-surface-border p-3 text-xs"><h4 className="break-words font-semibold">{quote.field_path || 'Document evidence'}</h4><div className="mt-2 flex flex-wrap gap-1.5">{pages.map(page => <button key={page} type="button" className="paper-source-link" aria-label={`Open evidence page ${page}`} disabled={!onNavigate} onClick={() => onNavigate?.(page)}>Page {page}</button>)}</div><blockquote className="mt-2 whitespace-pre-wrap break-words border-l-2 border-brand pl-3 leading-relaxed">{quote.quote || 'No quotation returned.'}</blockquote>{(!pages.length || unresolved.length > 0) && <p className="mt-2 text-amber-700 dark:text-amber-400">{!pages.length ? 'No unique link to the attached original. Review the source manually.' : 'Some source references could not be linked to this original.'}</p>}<details className="paper-disclosure mt-2 !p-2 text-ink-faint"><summary className="!text-xs">Citation details</summary><p className="mt-2 break-all">Source IDs: {(quote.source_ids || []).join(', ') || 'None returned'}</p>{item.document_id && <p className="mt-1 break-all">Document: {item.document_id}</p>}{unresolved.length > 0 && <p className="mt-1 break-all">Unresolved: {unresolved.join(', ')}</p>}</details></article>
          })}</div>
          {!filtered.evidence.length && <p className="paper-notice !text-xs">No citations match this view. Try Show all or clear the search. Missing citations still require source review.</p>}
        </>}
        {panelState.panel === 'warnings' && <>
          <p className="mb-3 text-xs text-ink-muted">{filtered.warnings.length} warning(s). Viewing warnings does not acknowledge them for approval.</p>
          <div className="space-y-3">{filtered.warnings.map((issue, index) => <article key={index} className="min-w-0 rounded-lg border border-amber-500/20 bg-amber-500/5 p-3 text-xs"><h4 className="break-words font-semibold">{typeof issue === 'string' ? 'Source warning' : issue.code || 'Review warning'}</h4><p className="mt-1 whitespace-pre-wrap break-words">{typeof issue === 'string' ? issue : issue.message || 'Review this extraction warning.'}</p>{issue.field_path && <p className="mt-2 break-all text-ink-muted">{issue.field_path}</p>}{record && Number.isInteger(issue.page_number) && issue.page_number > 0 && issue.page_number <= pageCount(record) && onNavigate && <button type="button" className="paper-source-link mt-2" onClick={() => onNavigate(issue.page_number)}>Page {issue.page_number}</button>}<details className="paper-disclosure mt-2 !p-2"><summary className="!text-xs">Warning details</summary><pre className="mt-2 whitespace-pre-wrap break-words text-xs">{JSON.stringify(issue, null, 2)}</pre></details></article>)}</div>
          {!filtered.warnings.length && <p className="paper-notice !text-xs">No warnings match this view.</p>}
        </>}
        {panelState.panel === 'sources' && <div className="space-y-3 text-xs">
          <p className="text-ink-muted">{sourceIds.length} source document(s) · {evidence.length} citation(s) · {warnings.length} warning(s).</p>
          {record ? <div className="rounded-lg border border-surface-border p-3"><strong className="break-words">{record.filename}</strong><p className="mt-1 text-ink-muted">Original PDF attached to this review. Use page shortcuts to compare the source.</p></div> : <p className="paper-notice !text-xs">No original preview is attached here. Open the matching upload in Documents to compare its PDF. Source references below are retained; page numbers are not guessed.</p>}
          <details className="paper-disclosure !p-3"><summary className="!text-xs">Source document references ({sourceIds.length})</summary><ul className="mt-2 space-y-2">{sourceIds.map(id => <li key={id} className="break-all">{id}</li>)}</ul>{!sourceIds.length && <p className="mt-2 text-ink-muted">No source references supplied yet.</p>}</details>
          <p className="text-ink-muted">Draft edits keep the original extraction intact. Saving a draft and approving a version are separate actions.</p>
        </div>}
      </div>
    </section>}
    <p className="paper-review-tools-label">Review tools</p>
    <nav ref={toolbar} className="paper-review-tools" aria-label="Evidence and source review">
      {tabs.map(({ id, label, count, icon: Icon }) => <button key={id} type="button" aria-label={`${label} (${count})`} aria-expanded={panelState.panel === id} aria-controls={panelId} className={panelState.panel === id ? 'is-active' : ''} onClick={event => open(event, id)}><Icon size={15} aria-hidden="true" /><span>{label}</span><span className={id === 'warnings' && count ? 'text-amber-700 dark:text-amber-400' : 'text-ink-faint'}>{count}</span></button>)}
    </nav>
  </aside>
}
