import { useEffect, useRef, useState } from 'react'
import { ChevronLeft, ChevronRight, ExternalLink } from 'lucide-react'
import { usePaperApi } from '../../hooks/usePaperApi'
import { pageCount, reviewPage } from '../../paper/sourceReview'
import { extractionWarnings } from '../../paper/extractionDraft'
import FieldSourceLinks, { FieldSourceContext } from './FieldSourceLinks'
import ReviewInspector from './ReviewInspector'

/** Faithful source pages beside an unchanged, mounted canonical field editor. */
export default function SourceReview({ record, children, evidence, warnings, fieldData, sourceDocumentIds = [], editable = false, fieldsLabel = 'Canonical fields' }) {
  const paperApi = usePaperApi()
  const [page, setPage] = useState(1)
  const [pane, setPane] = useState('fields')
  const [scope, setScope] = useState(editable ? 'all' : 'page')
  const [zoom, setZoom] = useState(100)
  const [loadedUrl, setLoadedUrl] = useState('')
  const [failedUrl, setFailedUrl] = useState('')
  const [reload, setReload] = useState(0)
  const [sourceFocus, setSourceFocus] = useState('')
  const [inspector, setInspector] = useState({ panel: '', fieldPath: '', label: '', fieldEvidence: null })
  const viewer = useRef(null)
  const reviewHost = useRef(null)
  const returnTarget = useRef(null)
  const originalScroll = useRef(null)
  const extractedPane = useRef(null)
  const total = pageCount(record)
  const pageUrl = record ? paperApi.extractionPageUrl(record.job_id, Math.min(page, total)) : ''
  const sourceUrl = pageUrl && reload ? `${pageUrl}?retry=${reload}` : pageUrl

  useEffect(() => { setPage(1); setPane('fields'); setZoom(100); setScope(editable ? 'all' : 'page'); setSourceFocus('') }, [record?.job_id, editable])
  useEffect(() => { setInspector({ panel: '', fieldPath: '', label: '', fieldEvidence: null }); returnTarget.current = null }, [record?.job_id, evidence, editable])
  useEffect(() => {
    originalScroll.current?.scrollTo({ top: 0, left: 0, behavior: 'auto' })
    extractedPane.current?.scrollTo({ top: 0, behavior: 'auto' })
  }, [record?.job_id, page])
  const failed = failedUrl === sourceUrl
  const loading = loadedUrl !== sourceUrl && !failed
  const quotes = evidence ?? record?.result?.fields?.evidence ?? []
  const issues = warnings ?? extractionWarnings(record)
  const currentPage = Math.min(page, total)
  const pageData = reviewPage(record, currentPage, { evidence: quotes, data: fieldData })
  const changePage = next => {
    setPage(Math.max(1, Math.min(total, Math.trunc(Number(next)) || 1)))
    setScope('page')
    setSourceFocus('')
  }
  const inspectField = details => {
    returnTarget.current = details.returnTarget || null
    setInspector({ panel: 'evidence', fieldPath: details.fieldPath, label: details.label, fieldEvidence: details.evidence === quotes ? null : details.evidence ?? null })
  }
  const jumpField = (next, label, details) => {
    setPage(Math.max(1, Math.min(total, next)))
    setSourceFocus(label)
    setPane('original')
    if (details) inspectField(details)
    const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    requestAnimationFrame(() => {
      viewer.current?.focus({ preventScroll: true })
      viewer.current?.scrollIntoView({ block: 'nearest', behavior: reducedMotion ? 'auto' : 'smooth' })
    })
  }
  const backToField = () => {
    setPane('fields')
    setScope('all')
    setInspector(current => ({ ...current, panel: '' }))
    requestAnimationFrame(() => {
      const retained = returnTarget.current
      const candidates = [...(reviewHost.current?.querySelectorAll('[data-review-field]') || [])]
      const card = candidates.find(node => node.dataset.reviewField === inspector.fieldPath) || candidates.filter(node => inspector.fieldPath.startsWith(`${node.dataset.reviewField}/`)).sort((a, b) => b.dataset.reviewField.length - a.dataset.reviewField.length)[0]
      const target = retained?.isConnected ? retained : card?.querySelector('input, select, textarea, button, summary') || card
      if (!target) return
      let ancestor = target.parentElement
      while (ancestor) { if (ancestor.tagName === 'DETAILS') ancestor.open = true; ancestor = ancestor.parentElement }
      target.focus({ preventScroll: true })
      target.scrollIntoView({ block: 'center', behavior: window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' })
    })
  }

  return <FieldSourceContext.Provider value={{ record, evidence: quotes, onJump: jumpField, onInspect: inspectField }}><section ref={reviewHost} className="paper-review-host min-w-0 space-y-3" aria-label="Original document and canonical fields">
    {record && <div className="min-w-0 rounded-lg border border-brand/20 bg-brand/5 p-3 text-xs text-ink-muted"><div className="flex min-w-0 flex-wrap items-center justify-between gap-2"><strong className="min-w-0 break-words text-sm text-ink">Review against {record.filename}</strong>{issues.length > 0 && <button type="button" className="paper-source-link !text-amber-700 dark:!text-amber-400" onClick={() => setInspector({ panel: 'warnings', fieldPath: '', label: '', fieldEvidence: null })}>{issues.length} extraction warnings</button>}</div><p className="mt-1">Use Review tools for evidence, warnings and source references from anywhere in this review.</p></div>}
    {record && <div className="flex flex-wrap gap-2 lg:hidden" role="group" aria-label="Source review view">
      <button type="button" aria-pressed={pane === 'original'} className={pane === 'original' ? 'paper-primary' : 'paper-secondary'} onClick={() => setPane('original')}>Original</button>
      <button type="button" aria-pressed={pane === 'fields'} className={pane === 'fields' ? 'paper-primary' : 'paper-secondary'} onClick={() => setPane('fields')}>Extracted</button>
    </div>}
    {record && sourceFocus && <p role="status" className="text-xs text-brand">Showing source page {currentPage} for {sourceFocus}. {editable ? 'Your draft edits are retained.' : 'All fields remain available.'}</p>}
    <div className={`grid min-w-0 grid-cols-1 items-start gap-4 ${record ? 'lg:grid-cols-2' : ''}`}>
      {record && <div ref={viewer} role="region" tabIndex={-1} className={`min-w-0 rounded-xl border border-surface-border bg-surface p-3 focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand lg:sticky lg:top-4 ${scope === 'page' ? 'lg:flex lg:h-[75vh] lg:max-h-[calc(100vh-2rem)] lg:flex-col' : ''} ${pane === 'original' ? 'block' : 'hidden lg:block'}`} aria-label="Original PDF page viewer">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <button type="button" className="paper-secondary !p-2" aria-label="Previous original page" disabled={page <= 1} onClick={() => changePage(page - 1)}><ChevronLeft size={16} /></button>
          <label className="flex items-center gap-1 text-xs text-ink-muted">Page <input aria-label="Original PDF page number" type="number" min={1} max={total} value={Math.min(page, total)} className="paper-input !w-16 !px-2 !py-1" onChange={event => changePage(event.target.value)} /><span>of {total}</span></label>
          <button type="button" className="paper-secondary !p-2" aria-label="Next original page" disabled={page >= total} onClick={() => changePage(page + 1)}><ChevronRight size={16} /></button>
          <select aria-label="Zoom original page" className="paper-input !w-auto !px-2 !py-1 text-xs" value={zoom} onChange={event => setZoom(Number(event.target.value))}><option value={100}>Fit width</option><option value={125}>125%</option><option value={150}>150%</option><option value={200}>200%</option></select>
        </div>
        {loading && !failed && <p role="status" className="mb-2 text-xs text-ink-muted">Loading original page…</p>}
        {failed && <div className="mb-3 space-y-2"><p role="alert" className="text-xs text-ink-muted">Page unavailable. Retry or open the original PDF.</p><button type="button" className="paper-secondary" onClick={() => setReload(current => current + 1)}>Retry original page</button></div>}
        <div ref={originalScroll} className={`max-h-[65vh] overflow-auto rounded border border-surface-border bg-white ${scope === 'page' ? 'lg:min-h-0 lg:flex-1' : ''}`}>
          <img key={sourceUrl} src={sourceUrl} crossOrigin="use-credentials" alt={`Original ${record.filename}, page ${Math.min(page, total)}`} className={failed ? 'hidden' : 'paper-enter block h-auto'} style={{ width: `${zoom}%`, maxWidth: 'none' }} onLoad={() => { setLoadedUrl(sourceUrl); setFailedUrl('') }} onError={() => setFailedUrl(sourceUrl)} />
        </div>
        <a className="mt-3 inline-flex items-center gap-1 text-xs text-brand underline" href={`${paperApi.extractionFileUrl(record.job_id)}#page=${Math.min(page, total)}`} target="_blank" rel="noreferrer"><ExternalLink size={13} /> Open original PDF</a>
      </div>}
      <div ref={extractedPane} role="region" className={`min-w-0 space-y-4 ${record && scope === 'page' ? 'lg:sticky lg:top-4 lg:h-[75vh] lg:max-h-[calc(100vh-2rem)] lg:overflow-auto lg:pr-1' : ''} ${!record || pane === 'fields' ? 'block' : 'hidden lg:block'}`} aria-label={fieldsLabel}>
        {record && <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-surface-border bg-surface p-3">
          <div role="group" aria-label="Extracted review scope" className="flex flex-wrap gap-2"><button type="button" aria-pressed={scope === 'page'} className={scope === 'page' ? 'paper-primary !px-2 !py-1.5 !text-xs' : 'paper-secondary !px-2 !py-1.5 !text-xs'} onClick={() => setScope('page')}>This page</button><button type="button" aria-pressed={scope === 'all'} className={scope === 'all' ? 'paper-primary !px-2 !py-1.5 !text-xs' : 'paper-secondary !px-2 !py-1.5 !text-xs'} onClick={() => setScope('all')}>{editable ? 'Edit all fields' : 'All fields'}</button></div>
          <div className="flex items-center gap-2"><button type="button" className="paper-secondary !p-1.5" aria-label="Previous extracted page" disabled={currentPage <= 1} onClick={() => changePage(currentPage - 1)}><ChevronLeft size={15} /></button><span className="text-xs text-ink-muted" role="status">Page {currentPage} of {total}</span><button type="button" className="paper-secondary !p-1.5" aria-label="Next extracted page" disabled={currentPage >= total} onClick={() => changePage(currentPage + 1)}><ChevronRight size={15} /></button></div>
        </div>}
        {record && scope === 'page' && <PageExtraction key={currentPage} pageNumber={currentPage} content={pageData} editable={editable} />}
        <div hidden={Boolean(record) && scope !== 'all'}>{children}</div>
      </div>
    </div>
    {(record || quotes.length > 0 || issues.length > 0 || sourceDocumentIds.length > 0) && <ReviewInspector record={record} evidence={quotes} warnings={issues} sourceDocumentIds={sourceDocumentIds} pageNumber={currentPage} state={inspector} onChange={setInspector} onNavigate={record ? next => jumpField(next, inspector.label || 'selected evidence') : undefined} onReturnToField={inspector.fieldPath ? backToField : undefined} />}
  </section></FieldSourceContext.Provider>
}

function FieldValue({ value }) {
  if (value == null || value === '') return <span className="italic text-ink-faint">Unknown</span>
  if (typeof value === 'object') return <details className="paper-disclosure"><summary className="text-xs">View structured value</summary><pre className="mt-2 overflow-auto whitespace-pre-wrap break-words text-xs">{JSON.stringify(value, null, 2)}</pre></details>
  return String(value)
}

function FieldValues({ fields }) {
  return <dl className="mt-3 grid min-w-0 grid-cols-[repeat(auto-fit,minmax(min(100%,200px),1fr))] gap-3">{fields.map(({ fieldPath, value }) => {
    const label = fieldPath.replace(/^\//, '').split('/').map(token => token.replaceAll('~1', '/').replaceAll('~0', '~').replaceAll('_', ' ')).join(' / ')
    return <div key={fieldPath} data-review-field={fieldPath} className={`min-w-0 rounded-lg bg-surface-muted p-3 ${value !== null && typeof value === 'object' || String(value ?? '').length > 140 ? 'col-span-full' : ''}`}><dt className="flex flex-wrap items-start justify-between gap-2"><span className="break-words text-xs font-medium text-ink-muted">{label}</span><FieldSourceLinks fieldPath={fieldPath} label={label} /></dt><dd className="mt-1 whitespace-pre-wrap break-words text-sm"><FieldValue value={value} /></dd></div>
  })}</dl>
}

function PageExtraction({ pageNumber, content, editable }) {
  const tables = content.page?.tables || []
  const images = content.page?.images || []
  return <section className="min-w-0 space-y-4 rounded-xl border border-surface-border bg-surface p-3" aria-label={`Extracted page ${pageNumber}`}>
    <div><h4 className="font-semibold">Extracted page {pageNumber}</h4><p className="mt-1 text-xs text-ink-muted">{content.page ? 'Stored page content and fields with exact source links.' : 'This original page has no stored extraction. No content from another page is substituted.'}</p></div>
    {content.page && <div><h5 className="text-xs font-semibold">Recovered text</h5><div className="mt-2 whitespace-pre-wrap break-words rounded-lg bg-surface-muted p-3 text-sm leading-relaxed" data-extracted-page={pageNumber}>{content.text || 'No text was recovered on this page. Inspect the original image and warnings.'}</div></div>}
    {!!content.fields.length && <div><h5 className="text-xs font-semibold">{editable ? 'Current draft values referenced on this page' : 'Fields referenced on this page'}</h5>{editable && <p className="mt-1 text-xs text-ink-muted">Edited values retain their earlier citations; verify every change against the source.</p>}<FieldValues fields={content.fields} /></div>}
    {tables.map((table, index) => <div key={table.table_id || index} className="min-w-0 overflow-auto rounded-lg border border-surface-border"><table className="w-full text-left text-xs"><caption className="p-2 text-left font-medium">Table {index + 1} · page {pageNumber}</caption><tbody>{(table.rows || []).map((row, rowIndex) => <tr key={rowIndex}>{row.map((cell, cellIndex) => <td key={cellIndex} className="whitespace-pre-wrap border border-surface-border p-2 align-top">{cell ?? '—'}</td>)}</tr>)}</tbody></table></div>)}
    {!!images.length && <p className="text-xs text-ink-muted">{images.length} extracted visual asset(s) on this page. Inspect the original for appearance and layout.</p>}
    {!content.fields.length && <p className="text-xs text-ink-muted">No canonical fields link uniquely to this page. Use {editable ? 'Edit all fields' : 'All fields'} to inspect the complete document.</p>}
  </section>
}

/** Read-only canonical values remain separate from the immutable extraction JSON. */
export function ExtractedFields({ data, onEdit }) {
  if (!data) return <p className="paper-notice">No fields returned. Prepare an empty draft and enter values verified against the source.</p>
  return <div className="min-w-0 rounded-xl border border-surface-border bg-surface p-3"><div className="flex flex-wrap items-center justify-between gap-2"><h4 className="font-semibold">Extracted fields</h4>{onEdit && <button type="button" className="paper-primary !px-3 !py-1.5 !text-xs" onClick={onEdit}>Review / edit</button>}</div><p className="mt-2 text-xs text-ink-muted">Evidence opens this field’s quotes in Review tools. Page shortcuts open the original alongside its evidence; Back to field returns to your place.</p><FieldValues fields={Object.entries(data).map(([key, value]) => ({ fieldPath: `/${key.replaceAll('~', '~0').replaceAll('/', '~1')}`, value }))} /></div>
}
