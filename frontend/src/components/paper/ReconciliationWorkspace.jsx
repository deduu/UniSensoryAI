import { useEffect, useRef, useState } from 'react'
import { ArrowLeft, ChevronLeft, ChevronRight, ExternalLink, FileSearch, RefreshCw, X } from 'lucide-react'
import { buildComparison, comparisonCitations, loadComparisonResources } from '../../paper/reconciliationComparison'
import { evidencePages, pageCount } from '../../paper/sourceReview'
import { formatStatus } from '../../paper/helpers'
import { formatMoney } from '../../paper/money'

const RESULT_LABELS = { blocking: 'Issue reported', review: 'Needs review', reported: 'No finding reported', unknown: 'Data unavailable', unavailable: 'No authority' }

function Finding({ finding }) {
  return <div className="space-y-1 text-xs"><strong>{formatStatus(finding.code)}</strong><p className="leading-5 text-ink-muted">{finding.message}</p></div>
}

/** Keep literal source equality separate from the historical reconciliation findings. */
export function ComparisonResult({ row, ready, referenceOnly }) {
  if (!ready) return <span className="paper-comparison-result">Loading reference</span>
  const result = row.kind === 'contract_diagnostic' ? 'Retained contract diagnostic'
    : referenceOnly && row.status === 'unavailable' ? 'Not assessed against contract' : RESULT_LABELS[row.status]
  return <div className="space-y-3">
    {row.valueComparison && <div><p className="mb-1 text-[11px] text-ink-muted">Field values</p><span className={`paper-comparison-result is-${row.valueComparison.status}`}>{row.valueComparison.label}</span></div>}
    <div><p className="mb-1 text-[11px] text-ink-muted">Saved result</p><span className={`paper-comparison-result is-${row.status}`}>{result}</span>
      {row.findings.length > 0 && <details className="mt-2"><summary className="!text-xs">{row.findings.length} finding{row.findings.length === 1 ? '' : 's'}</summary><div className="mt-3 space-y-3">{row.findings.map((finding, index) => <Finding key={index} finding={finding} />)}</div></details>}
    </div>
    {row.note && <details><summary className="!text-xs">Details</summary><p className="mt-2 text-xs leading-5 text-ink-muted">{row.note}</p></details>}
  </div>
}

export function Values({ values }) {
  return <dl className="space-y-2">{values.map(item => {
    const characters = !item.monetary && typeof item.value === 'string' ? Array.from(item.value) : []
    return <div key={item.label}><dt className="text-[11px] text-ink-muted">{item.label}</dt><dd className="mt-0.5 whitespace-pre-wrap break-words text-sm font-medium">{item.value === null || item.value === undefined || item.value === '' ? <span className="font-normal italic text-ink-faint">Unknown</span> : item.monetary ? formatMoney(item.value, item.currency) : characters.length > 320 ? <>
      <p className="whitespace-normal font-normal text-ink-muted">{characters.slice(0, 160).join('')}…</p>
      <details className="mt-2"><summary className="cursor-pointer text-xs font-medium text-brand">Read full {item.label.toLowerCase()}</summary><p className="mt-2 whitespace-pre-wrap break-words font-normal">{item.value}</p></details>
    </> : String(item.value)}</dd></div>
  })}</dl>
}

function SourceCell({ side, row, values, sources, documentIds, evidence, onInspect }) {
  const paths = side === 'contract' ? row.contractPaths : row.invoicePaths
  const links = comparisonCitations(sources, paths, evidence, documentIds, side === 'contract')
  return <div className="min-w-0 space-y-3"><Values values={values} />
    <div className="flex flex-wrap gap-1" aria-label={`${row.label} ${side} sources`}>
      {links.map(link => <button key={`${link.documentId}-${link.page}`} type="button" className="paper-source-link" aria-label={`Inspect ${side} ${row.label}, page ${link.page}${documentIds.length > 1 ? `, ${link.record.filename}` : ''}`} title={link.record.filename} onClick={event => onInspect({ side, row, documentId: link.documentId, page: link.page, returnTarget: event.currentTarget })}><FileSearch size={12} aria-hidden="true" />{documentIds.length > 1 ? `${link.record.filename} · ` : ''}p. {link.page}</button>)}
      {!links.length && <span className="text-[11px] text-ink-faint">No exact page citation</span>}
      {links.some(link => link.unresolved.length) && <span className="text-[11px] text-ink-faint">Some citations unresolved</span>}
      <button type="button" className="paper-text-action text-[11px]" disabled={!documentIds.length} onClick={event => onInspect({ side, row, documentId: links[0]?.documentId || documentIds[0], page: links[0]?.page || 1, returnTarget: event.currentTarget })}>Inspect {side}</button>
    </div>
  </div>
}

/** Inspect either original without leaving the comparison or losing the selected row. */
function ComparisonSourceViewer({ api, sources, selection, contractIds, invoiceId, contractEvidence, invoiceEvidence, onSelect, onBack, onClose }) {
  const scroll = useRef(null)
  const ids = selection.side === 'contract' ? contractIds : [invoiceId].filter(Boolean)
  const source = sources.find(item => item.documentId === selection.documentId)
  const record = source?.record
  const total = pageCount(record)
  const page = Math.min(selection.page, total)
  const url = record ? api.extractionPageUrl(record.job_id, page) : ''
  const [loaded, setLoaded] = useState('')
  const [failed, setFailed] = useState('')
  const [retry, setRetry] = useState(0)
  const [zoom, setZoom] = useState(100)
  const sourceUrl = url && retry ? `${url}?retry=${retry}` : url
  useEffect(() => { scroll.current?.scrollTo({ top: 0, left: 0, behavior: 'auto' }) }, [sourceUrl])
  const paths = selection.side === 'contract' ? selection.row.contractPaths : selection.row.invoicePaths
  const evidence = selection.side === 'contract' ? contractEvidence.filter(item => item.document_id === selection.documentId) : invoiceEvidence.filter(item => !item.document_id || item.document_id === selection.documentId)
  const quotes = evidence.filter(item => { const quote = item.evidence || item; return paths.some(path => quote.field_path === path || quote.field_path?.startsWith(`${path}/`)) })
  const switchSide = side => {
    const nextIds = side === 'contract' ? contractIds : [invoiceId].filter(Boolean)
    const nextPaths = side === 'contract' ? selection.row.contractPaths : selection.row.invoicePaths
    const nextEvidence = side === 'contract' ? contractEvidence : invoiceEvidence
    const links = comparisonCitations(sources, nextPaths, nextEvidence, nextIds, side === 'contract')
    onSelect({ ...selection, side, documentId: links[0]?.documentId || nextIds[0], page: links[0]?.page || 1 })
  }
  const setPage = value => onSelect({ ...selection, page: Math.max(1, Math.min(total, Math.trunc(Number(value)) || 1)) })
  return <aside className="paper-comparison-source paper-panel" aria-label="Comparison source inspector">
    <header className="space-y-3 border-b border-surface-border p-3">
      <div className="flex items-center justify-between gap-2"><div className="min-w-0"><h4 className="truncate text-sm font-semibold">{selection.row.label}</h4><p className="text-[11px] text-ink-muted">Original PDF and retained field evidence</p></div><button type="button" className="paper-secondary !p-1.5" aria-label="Close source inspector" onClick={onClose}><X size={14} /></button></div>
      <div role="group" aria-label="Comparison document" className="flex gap-2">{['contract', 'invoice'].map(side => <button key={side} type="button" aria-pressed={side === selection.side} className={`${side === selection.side ? 'paper-primary' : 'paper-secondary'} !px-3 !py-1.5 !text-xs`} disabled={side === 'contract' ? !contractIds.length : !invoiceId} onClick={() => switchSide(side)}>{side === 'contract' ? 'Contract' : 'Invoice'}</button>)}</div>
      {ids.length > 1 ? <label className="block text-[11px] text-ink-muted">Source document<select className="paper-input mt-1 !py-1.5" value={selection.documentId} onChange={event => onSelect({ ...selection, documentId: event.target.value, page: 1 })}>{ids.map(id => <option key={id} value={id}>{sources.find(item => item.documentId === id)?.record?.filename || id}</option>)}</select></label> : <p className="break-words text-xs text-ink-muted">{record?.filename || 'Source document unavailable'}</p>}
      {record && <div className="flex flex-wrap items-center gap-2"><button type="button" className="paper-secondary !p-1.5" aria-label="Previous comparison source page" disabled={page <= 1} onClick={() => setPage(page - 1)}><ChevronLeft size={14} /></button><label className="flex items-center gap-1 text-xs text-ink-muted">Page <input aria-label="Comparison source page number" className="paper-input !w-14 !px-1.5 !py-1" type="number" min={1} max={total} value={page} onChange={event => setPage(event.target.value)} />of {total}</label><button type="button" className="paper-secondary !p-1.5" aria-label="Next comparison source page" disabled={page >= total} onClick={() => setPage(page + 1)}><ChevronRight size={14} /></button><a className="paper-text-action text-xs" href={`${api.extractionFileUrl(record.job_id)}#page=${page}`} target="_blank" rel="noreferrer"><ExternalLink size={12} />Open PDF</a></div>}
      {record && <select aria-label="Zoom comparison source page" className="paper-input !w-auto !px-2 !py-1 !text-xs" value={zoom} onChange={event => setZoom(Number(event.target.value))}><option value={100}>Fit width</option><option value={125}>125%</option><option value={150}>150%</option><option value={200}>200%</option></select>}
    </header>
    {!record ? <p role="status" className="p-4 text-xs leading-5 text-ink-muted">{source?.error || 'No stored PDF is available for this source.'}</p> : <div className="min-h-0 flex-1 overflow-auto bg-surface-muted p-2" ref={scroll}>
      {loaded !== sourceUrl && failed !== sourceUrl && <p role="status" className="p-2 text-xs text-ink-muted">Loading original page…</p>}
      {failed === sourceUrl && <div className="space-y-2 p-2"><p role="alert" className="text-xs text-ink-muted">Original page unavailable. Retry or open the PDF.</p><button type="button" className="paper-secondary" onClick={() => setRetry(current => current + 1)}>Retry page</button></div>}
      <img key={sourceUrl} src={sourceUrl} crossOrigin="use-credentials" alt={`Original ${selection.side} ${record.filename}, page ${page}`} className={failed === sourceUrl ? 'hidden' : 'block h-auto bg-white'} style={{ width: `${zoom}%`, maxWidth: 'none' }} onLoad={() => setLoaded(sourceUrl)} onError={() => setFailed(sourceUrl)} />
    </div>}
    <details className="paper-comparison-quotes border-t border-surface-border p-3" open><summary className="text-xs">Field evidence · {quotes.length} citation{quotes.length === 1 ? '' : 's'}</summary><div className="mt-2 max-h-32 space-y-3 overflow-auto">{quotes.length ? quotes.map((item, index) => {
      const quote = item.evidence || item
      const citation = evidencePages(record, item)
      return <div key={index} className="space-y-1 text-xs"><p className="break-all text-[11px] text-ink-faint">{quote.field_path}</p><blockquote className="whitespace-pre-wrap break-words border-l-2 border-brand/30 pl-2 leading-5">{quote.quote || 'No quote was stored.'}</blockquote><div className="flex flex-wrap gap-1">{citation.pages.map(number => <button type="button" key={number} className="paper-source-link" onClick={() => setPage(number)}>p. {number}</button>)}</div>{citation.unresolved.length > 0 && <p className="text-[11px] text-amber-700 dark:text-amber-300">{citation.unresolved.length} source reference(s) have no unique page link.</p>}</div>
    }) : <p className="text-xs leading-5 text-ink-muted">No exact citation for these values. Inspect the PDF manually. Reviewed values may differ from the retained extraction quotes.</p>}<p className="text-[11px] leading-4 text-ink-faint">Citations locate source material; they do not verify its meaning. Quotes may span multiple pages.</p></div></details>
    <div className="flex gap-2 border-t border-surface-border p-3"><button type="button" className="paper-secondary w-full !py-1.5 !text-xs" onClick={onBack}><ArrowLeft size={13} />Back to comparison row</button></div>
  </aside>
}

/** A read-only saved assessment with exact authority or an explicitly unverified selected reference. */
export default function ReconciliationWorkspace({ version, api, onCorrect, canCorrect = false }) {
  const [resources, setResources] = useState(null)
  const [reload, setReload] = useState(0)
  const [filter, setFilter] = useState('all')
  const [selection, setSelection] = useState(null)
  const [compact, setCompact] = useState(() => window.matchMedia('(max-width: 1023px)').matches)
  const returnTarget = useRef(null)
  const viewer = useRef(null)
  const host = useRef(null)
  useEffect(() => {
    const query = window.matchMedia('(max-width: 1023px)')
    const update = () => setCompact(query.matches)
    query.addEventListener('change', update)
    return () => query.removeEventListener('change', update)
  }, [])
  useEffect(() => {
    let active = true
    setSelection(null)
    loadComparisonResources(api, version).then(result => { if (active) setResources({ ...result, version, api, reload }) })
    return () => { active = false }
  }, [api, version, reload])
  const ready = resources?.version === version && resources?.api === api && resources?.reload === reload
  useEffect(() => { if (compact && selection && ready && viewer.current && !viewer.current.open) viewer.current.showModal() }, [compact, selection, ready])
  const data = ready ? resources : { agreement: null, selectedAgreement: null, agreementError: '', sources: [] }
  const comparison = buildComparison(version, data.agreement || data.selectedAgreement)
  const referenceOnly = comparison.mode === 'reference'
  const contractIds = comparison.contract?.draft.source_document_ids || []
  const invoiceId = version.package.invoice.source_document_id
  const contractEvidence = comparison.contract?.draft.evidence || []
  const invoiceEvidence = version.package.invoice.evidence || []
  const attention = row => row.status !== 'reported'
  const rows = filter === 'attention' ? comparison.rows.filter(attention) : comparison.rows
  const inspect = next => {
    returnTarget.current = next.returnTarget || returnTarget.current
    setSelection(next)
    requestAnimationFrame(() => {
      viewer.current?.focus({ preventScroll: true })
      if (window.matchMedia('(max-width: 1023px)').matches) viewer.current?.scrollIntoView({ block: 'start', behavior: 'auto' })
    })
  }
  const back = () => {
    const target = returnTarget.current?.isConnected ? returnTarget.current : host.current?.querySelector(`[data-comparison-row="${selection?.row.id}"] button`)
    const restore = () => { target?.focus({ preventScroll: true }); target?.scrollIntoView({ block: 'nearest', behavior: 'auto' }) }
    if (compact) { setSelection(null); requestAnimationFrame(restore) }
    else restore()
  }
  const ref = version.assessment.agreement_reference
  const Viewer = compact ? 'dialog' : 'div'
  const handleViewerKey = event => {
    if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); setSelection(null); back() }
    if (compact && event.key === 'Tab') {
      const controls = [...viewer.current.querySelectorAll('button:not(:disabled), a[href], input, select, summary')].filter(node => node.getClientRects().length)
      const first = controls[0]
      const last = controls[controls.length - 1]
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
    }
  }
  return <section ref={host} className="paper-panel min-w-0 space-y-4 p-4 sm:p-5" aria-label="Invoice and contract reconciliation workspace">
    <header className="flex flex-wrap items-start justify-between gap-3"><div className="min-w-0"><h3 className="text-lg font-semibold">Contract and invoice comparison</h3><p className="mt-1 text-xs leading-5 text-ink-muted">Invoice case v{version.version_number} · {ref ? `approved contract v${ref.version_number}` : referenceOnly ? `selected contract v${comparison.selectedAgreement.version_number} · reference only` : 'no approved contract reference'} · policy {version.assessment.policy_id} v{version.assessment.policy_version}</p></div><div className="flex flex-wrap gap-2"><span className={`paper-comparison-result ${!referenceOnly && version.assessment.outcome === 'matched' ? 'is-matched' : 'is-review'}`}>{formatStatus(version.assessment.outcome)}</span>{onCorrect && <button type="button" className="paper-secondary !text-xs" disabled={!canCorrect} onClick={onCorrect}>Correct / reassess</button>}</div></header>
    <p className="text-xs leading-5 text-ink-muted">“Values equal” compares displayed invoice and contract values only. Linked identities are reviewer-assigned, separate from extracted invoice fields. Saved results show the server’s findings; “No finding reported” does not prove that a field was checked.</p>
    {!ready && <p className="paper-loading !text-xs" role="status"><RefreshCw size={14} className="animate-spin" />Loading approved contract and source PDFs…</p>}
    {ready && data.agreementError && <p className="paper-notice" role="status">{data.agreementError}</p>}
    {referenceOnly && <div className="paper-notice space-y-1" role="status"><strong className="text-sm">Selected contract · coverage not verified</strong><p className="text-xs leading-5">These are stored values from the confirmed selected approved contract. Review invoice service coverage and reassess before using them as reconciliation expectations. Inspect either original PDF using the source shortcuts.</p></div>}
    {version.duplicate_of && <p className="paper-error">Duplicate package. Invoice approval is blocked.</p>}
    <div className="flex flex-wrap items-center justify-between gap-2"><div className="flex gap-2" role="group" aria-label="Comparison row filter"><button type="button" aria-pressed={filter === 'all'} className={`${filter === 'all' ? 'paper-primary' : 'paper-secondary'} !px-3 !py-1.5 !text-xs`} onClick={() => setFilter('all')}>All checks</button><button type="button" aria-pressed={filter === 'attention'} className={`${filter === 'attention' ? 'paper-primary' : 'paper-secondary'} !px-3 !py-1.5 !text-xs`} onClick={() => setFilter('attention')}>Needs attention ({comparison.rows.filter(attention).length})</button></div><button type="button" className="paper-text-action text-xs" disabled={!ready} onClick={() => setReload(current => current + 1)}><RefreshCw size={12} />Reload sources</button></div>
    <div className={`paper-comparison-grid ${selection && ready ? 'has-source' : ''}`}>
      <div className="paper-comparison-table-wrap" tabIndex={0} role="region" aria-label="Contract expectations and invoice values">
        <table className="paper-comparison-table"><thead><tr><th scope="col">Check</th><th scope="col">{referenceOnly ? 'Selected contract reference' : 'Approved contract expectation'}</th><th scope="col">Invoice value</th><th scope="col">Comparison / saved result</th></tr></thead><tbody>{rows.map(row => <tr key={row.id} data-comparison-row={row.id} className={selection?.row.id === row.id ? 'is-selected' : ''}><th scope="row">{row.label}</th><td><SourceCell side="contract" row={row} values={row.expected} sources={data.sources} documentIds={contractIds} evidence={contractEvidence} onInspect={inspect} /></td><td><SourceCell side="invoice" row={row} values={row.actual} sources={data.sources} documentIds={[invoiceId].filter(Boolean)} evidence={invoiceEvidence} onInspect={inspect} /></td><td><ComparisonResult row={row} ready={ready} referenceOnly={referenceOnly} /></td></tr>)}</tbody></table>
        {!rows.length && <p className="p-4 text-sm text-ink-muted">No comparison rows need attention. Review any additional findings below before deciding.</p>}
      </div>
      {selection && ready && <Viewer ref={viewer} tabIndex={-1} className="paper-comparison-viewer-focus" aria-label="Inspect contract and invoice sources" onCancel={event => { event.preventDefault(); setSelection(null); back() }} onKeyDown={handleViewerKey}><ComparisonSourceViewer api={api} sources={data.sources} selection={selection} contractIds={contractIds} invoiceId={invoiceId} contractEvidence={contractEvidence} invoiceEvidence={invoiceEvidence} onSelect={setSelection} onBack={back} onClose={() => { setSelection(null); back() }} /></Viewer>}
    </div>
    {!!comparison.otherFindings.length && <details className="paper-disclosure" open><summary>Additional findings ({comparison.otherFindings.length})</summary><div className="mt-3 grid gap-3 sm:grid-cols-2">{comparison.otherFindings.map((finding, index) => <Finding key={index} finding={finding} />)}</div></details>}
  </section>
}
