import { useEffect, useId, useRef, useState } from 'react'
import { AlertTriangle, ArrowUpLeft, Files, MessageSquareQuote, Search, X } from 'lucide-react'
import { projectReviewItems, reviewFieldValue } from '../../paper/sourceReview'
import { assessWarnings } from '../../paper/warningReview'
import { groupReviewIssues } from '../../paper/reviewIssueSummary'
import ReviewIssueList from './ReviewIssueList'
import CanonicalValue from './CanonicalValue'
import { fieldCurrency } from '../../paper/monetaryFields'
import './reviewWarnings.css'

const INITIAL_STATE = { panel: '', fieldPath: '', label: '', fieldEvidence: null }

/** Persistent, non-modal access to exact evidence, retained warnings and source references. */
export default function ReviewInspector({ record, evidence = [], warnings = [], sourceDocumentIds = [], pageNumber, state, onChange, onNavigate, onReturnToField, onInspectField, fieldData, baselineData }) {
  const [localState, setLocalState] = useState(INITIAL_STATE)
  const [query, setQuery] = useState('')
  const [pageOnly, setPageOnly] = useState(false)
  const [warningBucket, setWarningBucket] = useState('attention')
  const [valueFilter, setValueFilter] = useState('all')
  const panelState = state ?? localState
  const change = onChange ?? setLocalState
  const heading = useRef(null)
  const trigger = useRef(null)
  const toolbar = useRef(null)
  const panelId = useId()
  const collection = panelState.fieldEvidence ?? evidence
  const filtered = projectReviewItems(record, { evidence: collection, warnings, fieldPath: panelState.fieldPath, pageNumber: pageOnly ? pageNumber : null, query })
  const currentData = fieldData ?? record?.result?.fields?.data
  const warningReview = assessWarnings({ record, evidence, warnings, data: currentData, baselineData })
  const matchingWarnings = new Set(projectReviewItems(record, { evidence: [], warnings, fieldPath: panelState.fieldPath, query }).warnings)
  const filteredWarningItems = warningReview.items.filter(item => matchingWarnings.has(item.issue) && (!pageOnly || !item.pages.length || item.pages.includes(pageNumber)))
  const warningViews = [
    { id: 'attention', label: 'Needs review', count: filteredWarningItems.filter(item => item.status === 'attention').length },
    { id: 'history', label: 'Extraction history', count: filteredWarningItems.filter(item => item.status === 'history').length },
    { id: 'all', label: 'All diagnostics', count: filteredWarningItems.length },
  ]
  const visibleWarnings = filteredWarningItems.filter(item => warningBucket === 'all' || item.status === warningBucket)
  const issueGroups = groupReviewIssues(visibleWarnings, currentData)
  const missingGroups = issueGroups.filter(group => group.fieldPath && group.valueState !== 'present')
  const displayedGroups = warningBucket !== 'attention' || valueFilter === 'all' ? issueGroups : issueGroups.filter(group => valueFilter === 'missing' ? missingGroups.includes(group) : group.valueState === 'present')
  const sourceIds = [...new Set([...(record?.result?.document?.document_id ? [record.result.document.document_id] : []), ...sourceDocumentIds])]
  const tabs = [
    { id: 'evidence', label: 'Evidence', count: evidence.length, icon: MessageSquareQuote },
    { id: 'warnings', label: 'Review issues', count: warningReview.counts.attention, icon: AlertTriangle },
    { id: 'sources', label: 'Sources', count: sourceIds.length, icon: Files },
  ]
  const activeTab = tabs.find(tab => tab.id === panelState.panel)
  const currentValue = panelState.fieldPath ? reviewFieldValue(fieldData ?? record?.result?.fields?.data, panelState.fieldPath) : undefined

  useEffect(() => {
    if (panelState.panel) heading.current?.focus({ preventScroll: true })
    setQuery('')
    setPageOnly(false)
    setWarningBucket(panelState.warningBucket === 'history' ? 'history' : 'attention')
    setValueFilter('all')
  }, [panelState.panel, panelState.fieldPath, panelState.warningBucket, record?.job_id])

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
        <div className="min-w-0"><h3 ref={heading} tabIndex={-1} className="text-sm font-semibold focus:outline-none">{activeTab.label === 'Evidence' ? 'Field evidence' : activeTab.label === 'Sources' ? 'Source review' : 'Field review'}</h3><p className="mt-1 break-words text-xs text-ink-muted">{panelState.fieldPath ? `For ${panelState.label || panelState.fieldPath}` : record?.filename || 'Saved document review'}</p></div>
        <button type="button" aria-label="Close review inspector" className="paper-secondary !p-1.5" onClick={close}><X size={15} /></button>
      </header>
      {panelState.panel !== 'sources' && <div className="paper-review-inspector-filters space-y-2 border-b border-surface-border p-3">
        {panelState.fieldPath && <div className="flex flex-wrap items-center justify-between gap-2"><button type="button" className="paper-text-action text-xs" onClick={() => change({ ...panelState, fieldPath: '', label: '', fieldEvidence: null })}>Show all {panelState.panel}</button>{onReturnToField && <button type="button" className="paper-text-action text-xs" onClick={onReturnToField}><ArrowUpLeft size={13} /> Back to field</button>}</div>}
        <label className="relative block"><Search aria-hidden="true" size={14} className="pointer-events-none absolute left-2.5 top-2.5 text-ink-faint" /><input aria-label={`Search ${activeTab.label.toLowerCase()}`} type="search" className="paper-input !py-2 !pl-8 !text-xs" placeholder={panelState.panel === 'evidence' ? 'Find a field or quoted text' : 'Find a field or issue'} value={query} onChange={event => setQuery(event.target.value)} /></label>
        {record && Number.isInteger(pageNumber) && <label className="flex items-center gap-2 text-xs text-ink-muted"><input type="checkbox" className="rounded text-brand" checked={pageOnly} onChange={event => setPageOnly(event.target.checked)} /> Current PDF page only ({pageNumber})</label>}
        {panelState.panel === 'warnings' && <div className="paper-warning-views" role="group" aria-label="Warning log view">{warningViews.map(view => <button key={view.id} type="button" aria-pressed={warningBucket === view.id} className={warningBucket === view.id ? 'is-selected' : ''} onClick={() => setWarningBucket(view.id)}>{view.label} ({view.count})</button>)}</div>}
      </div>}
      <div className="paper-review-inspector-body" key={panelState.panel}>
        {panelState.panel === 'evidence' && <>
          {panelState.fieldPath && <section className="mb-3 rounded-lg bg-brand/5 p-3" aria-label="Current field value for comparison"><h4 className="mb-2 text-xs font-semibold">Current field value</h4><div className="max-h-36 overflow-auto whitespace-pre-wrap break-words text-sm">{currentValue === undefined ? <p className="text-ink-muted">This path is absent from the current fields. The retained citation may refer to an earlier candidate.</p> : <CanonicalValue value={currentValue} fieldPath={panelState.fieldPath} currency={fieldCurrency(fieldData ?? record?.result?.fields?.data, panelState.fieldPath)} formatted={typeof currentValue === 'string' && currentValue.length > 160} />}</div></section>}
          <p className="mb-3 text-xs text-ink-muted">{filtered.evidence.length} citation(s). Check the quote and complete conditions; a citation does not confirm an edited value.</p>
          <div className="space-y-3">{filtered.evidence.map(({ item, pages, unresolved }, index) => {
            const quote = item.evidence || item
            return <article key={index} className="min-w-0 rounded-lg border border-surface-border p-3 text-xs"><h4 className="break-words font-semibold">{quote.field_path || 'Document evidence'}</h4><div className="mt-2 flex flex-wrap gap-1.5">{pages.map(page => <button key={page} type="button" className="paper-source-link" aria-label={`Open evidence page ${page}`} disabled={!onNavigate} onClick={() => onNavigate?.(page)}>Page {page}</button>)}</div><blockquote className="mt-2 whitespace-pre-wrap break-words border-l-2 border-brand pl-3 leading-relaxed">{quote.quote || 'No quotation returned.'}</blockquote>{(!pages.length || unresolved.length > 0) && <p className="mt-2 text-amber-700 dark:text-amber-400">{!pages.length ? 'No unique link to the attached original. Review the source manually.' : 'Some source references could not be linked to this original.'}</p>}<details className="paper-disclosure mt-2 !p-2 text-ink-faint"><summary className="!text-xs">Citation details</summary><p className="mt-2 break-all">Source IDs: {(quote.source_ids || []).join(', ') || 'None returned'}</p>{item.document_id && <p className="mt-1 break-all">Document: {item.document_id}</p>}{unresolved.length > 0 && <p className="mt-1 break-all">Unresolved: {unresolved.join(', ')}</p>}</details></article>
          })}</div>
          {!filtered.evidence.length && <p className="paper-notice !text-xs">No citations match this view. Try Show all or clear the search. Missing citations still require source review.</p>}
        </>}
        {panelState.panel === 'warnings' && <>
          <p className="mb-2 text-xs text-ink-muted">{warningBucket === 'history' ? 'Earlier extraction diagnostics and corrections. Successful values are shown in All fields.' : 'Missing values and fields that still need source or reviewer checks.'}</p>
          {warningBucket === 'attention' && <div className="paper-warning-views mb-3" role="group" aria-label="Unresolved field filter">{[{ id: 'all', label: `All checks (${issueGroups.length})` }, { id: 'missing', label: `Missing values (${missingGroups.length})` }, { id: 'present', label: `Verify values (${issueGroups.filter(group => group.valueState === 'present').length})` }].map(view => <button key={view.id} type="button" aria-pressed={valueFilter === view.id} className={valueFilter === view.id ? 'is-selected' : ''} onClick={() => setValueFilter(view.id)}>{view.label}</button>)}</div>}
          <p role="status" className="mb-3 text-xs text-ink-faint">{displayedGroups.length} field or document checks shown. Details preserve the diagnostic log.</p>
          <ReviewIssueList groups={displayedGroups} record={record} data={currentData} onNavigate={onNavigate} onInspect={(fieldPath, label) => {
            const details = { fieldPath, label, fieldEvidence: null }
            if (onInspectField) onInspectField(details)
            else change({ ...panelState, ...details, panel: 'evidence' })
          }} />
          {!displayedGroups.length && <p className="paper-notice !text-xs">No entries match. Switch views or clear the filters.</p>}
          <details className="paper-disclosure mt-3 !p-2 text-xs text-ink-muted"><summary>About these statuses</summary><p className="mt-2">Needs review includes missing values and extracted values awaiting verification. Extraction history preserves earlier diagnostics; it does not certify successful extraction. Evidence contains quotations, while Sources lists original documents. Viewing entries does not acknowledge or resolve them for approval.</p></details>
        </>}
        {panelState.panel === 'sources' && <div className="space-y-3 text-xs">
          <p className="text-ink-muted">{sourceIds.length} original document(s) · {evidence.length} citation(s) · {warningReview.counts.attention} review issues · {warningReview.counts.history} historical log entries.</p>
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
