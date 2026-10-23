import { useEffect, useRef, useState } from 'react'
import { Check, ChevronLeft, ChevronRight, ExternalLink, FileSearch, RefreshCw, X } from 'lucide-react'
import { associationFingerprint, associationSignalPaths, associationSignalResult, candidateAllowed, confirmAssociation, loadAssociationResources } from '../../paper/contractAssociation'
import { comparisonCitations } from '../../paper/reconciliationComparison'
import { evidencePages, pageCount } from '../../paper/sourceReview'
import { formatError } from '../../paper/helpers'

const IDENTITY = ['vendor_id', 'store_id', 'contract_number']
const LABELS = { vendor_id: 'Vendor ID', store_id: 'Store ID', contract_number: 'Contract number' }
const shown = value => value === null || value === undefined || value === '' ? 'Unknown' : String(value)
const sameReference = (left, right) => left?.agreement_id === right?.agreement_id && left?.version_number === right?.version_number

function SignalResult({ signal }) {
  const result = associationSignalResult(signal)
  return <span className={`paper-comparison-result is-${result.tone}`}>{result.label}</span>
}

function SourceButtons({ side, signal, sources, ids, evidence, onInspect }) {
  const links = comparisonCitations(sources, associationSignalPaths(signal, side), evidence, ids, side === 'contract')
  return <div className="mt-2 flex flex-wrap gap-1" aria-label={`${signal.label} ${side} evidence`}>
    {links.map(link => <button key={`${link.documentId}-${link.page}`} type="button" className="paper-source-link" title={link.record.filename} aria-label={`Inspect ${side} ${signal.label}, ${link.record.filename}, page ${link.page}`} onClick={event => onInspect({ side, signal, documentId: link.documentId, page: link.page, returnTarget: event.currentTarget })}><FileSearch size={12} />{ids.length > 1 ? `${link.record.filename} · ` : ''}p. {link.page}</button>)}
    {!links.length && <span className="text-[11px] text-ink-faint">No exact page citation</span>}
    {links.some(link => link.unresolved.length) && <span className="text-[11px] text-amber-700">Some references unresolved</span>}
    <button type="button" className="paper-text-action text-[11px]" disabled={!ids.length} onClick={event => onInspect({ side, signal, documentId: links[0]?.documentId || ids[0], page: links[0]?.page || 1, returnTarget: event.currentTarget })}>Inspect {side}</button>
  </div>
}

function AssociationSource({ api, selection, sources, agreement, invoice, onSelect, onClose }) {
  const [zoom, setZoom] = useState(100)
  const [loaded, setLoaded] = useState('')
  const [failed, setFailed] = useState('')
  const [retry, setRetry] = useState(0)
  const scroll = useRef(null)
  const ids = selection.side === 'contract' ? [...new Set(agreement?.draft.source_document_ids || [])] : [invoice.source_document_id].filter(Boolean)
  const source = sources.find(item => item.documentId === selection.documentId)
  const record = source?.record
  const total = pageCount(record)
  const page = Math.max(1, Math.min(total, selection.page))
  const paths = associationSignalPaths(selection.signal, selection.side)
  const evidence = (selection.side === 'contract' ? agreement?.draft.evidence || [] : invoice.evidence || []).filter(item => selection.side === 'contract' ? item.document_id === selection.documentId : !item.document_id || item.document_id === selection.documentId)
  const quotes = evidence.filter(item => { const quote = item.evidence || item; return paths.some(path => quote.field_path === path || quote.field_path?.startsWith(`${path}/`)) })
  const url = record ? api.extractionPageUrl(record.job_id, page) : ''
  const imageUrl = retry ? `${url}?retry=${retry}` : url
  useEffect(() => { scroll.current?.scrollTo({ top: 0, left: 0, behavior: 'auto' }) }, [imageUrl])
  const setPage = value => onSelect({ ...selection, page: Math.max(1, Math.min(total, Math.trunc(Number(value)) || 1)) })
  const switchSide = side => {
    const nextIds = side === 'contract' ? agreement?.draft.source_document_ids || [] : [invoice.source_document_id].filter(Boolean)
    const nextEvidence = side === 'contract' ? agreement?.draft.evidence || [] : invoice.evidence || []
    const links = comparisonCitations(sources, associationSignalPaths(selection.signal, side), nextEvidence, nextIds, side === 'contract')
    onSelect({ ...selection, side, documentId: links[0]?.documentId || nextIds[0], page: links[0]?.page || 1 })
  }
  return <div className="flex min-h-0 flex-col" style={{ height: 'min(850px, 90dvh)' }}>
    <header className="shrink-0 space-y-3 border-b border-surface-border p-4">
      <div className="flex items-start justify-between gap-3"><div><h4 className="font-semibold">{selection.signal.label} · source review</h4><p className="mt-1 text-xs text-ink-muted">Inspect the original wording before confirming the contract.</p></div><button type="button" className="paper-secondary !p-2" aria-label="Close association source review" onClick={onClose}><X size={16} /></button></div>
      <div className="flex flex-wrap items-center gap-2"><div role="group" className="flex gap-2" aria-label="Association source document">{['invoice', 'contract'].map(side => <button key={side} type="button" className={`${selection.side === side ? 'paper-primary' : 'paper-secondary'} !px-3 !py-1.5 !text-xs`} aria-pressed={selection.side === side} disabled={side === 'contract' ? !agreement?.draft.source_document_ids?.length : !invoice.source_document_id} onClick={() => switchSide(side)}>{side === 'invoice' ? 'Invoice PDF' : 'Contract PDF'}</button>)}</div>
        {ids.length > 1 ? <label className="min-w-0 text-xs text-ink-muted">Document<select className="paper-input ml-2 !w-auto !max-w-80 !py-1" value={selection.documentId || ''} onChange={event => onSelect({ ...selection, documentId: event.target.value, page: 1 })}>{ids.map(id => <option key={id} value={id}>{sources.find(item => item.documentId === id)?.record?.filename || id}</option>)}</select></label> : <span className="min-w-0 break-words text-xs text-ink-muted">{record?.filename || 'Original document unavailable'}</span>}
      </div>
      {record && <div className="flex flex-wrap items-center gap-2"><button type="button" className="paper-secondary !p-1.5" aria-label="Previous association source page" disabled={page <= 1} onClick={() => setPage(page - 1)}><ChevronLeft size={14} /></button><label className="flex items-center gap-1 text-xs text-ink-muted">Page<input aria-label="Association source page number" type="number" className="paper-input !w-16 !px-2 !py-1" min={1} max={total} value={page} onChange={event => setPage(event.target.value)} />of {total}</label><button type="button" className="paper-secondary !p-1.5" aria-label="Next association source page" disabled={page >= total} onClick={() => setPage(page + 1)}><ChevronRight size={14} /></button><select aria-label="Association source zoom" className="paper-input !w-auto !py-1 !text-xs" value={zoom} onChange={event => setZoom(Number(event.target.value))}><option value={100}>Fit width</option><option value={125}>125%</option><option value={150}>150%</option><option value={200}>200%</option></select><a className="paper-text-action text-xs" href={`${api.extractionFileUrl(record.job_id)}#page=${page}`} target="_blank" rel="noreferrer"><ExternalLink size={12} />Open original PDF</a></div>}
    </header>
    <div ref={scroll} className="min-h-0 flex-1 overflow-auto bg-surface-muted p-3">{!record ? <p role="status" className="p-3 text-sm text-ink-muted">{source?.error || 'No stored PDF is available for this source.'}</p> : <>
      {loaded !== imageUrl && failed !== imageUrl && <p role="status" className="p-2 text-xs text-ink-muted">Loading original page…</p>}
      {failed === imageUrl && <div className="space-y-2 p-2"><p role="alert" className="text-sm text-ink-muted">Page preview unavailable. Retry or open the original PDF.</p><button type="button" className="paper-secondary" onClick={() => setRetry(value => value + 1)}>Retry page</button></div>}
      <img key={imageUrl} src={imageUrl} crossOrigin="use-credentials" alt={`Original ${selection.side}, ${record.filename}, page ${page}`} className={failed === imageUrl ? 'hidden' : 'block h-auto bg-white'} style={{ width: `${zoom}%`, maxWidth: 'none' }} onLoad={() => setLoaded(imageUrl)} onError={() => setFailed(imageUrl)} />
    </>}</div>
    <details className="shrink-0 border-t border-surface-border p-3" open><summary className="text-xs">Retained field evidence · {quotes.length} citation{quotes.length === 1 ? '' : 's'}</summary><div className="mt-2 max-h-36 space-y-3 overflow-auto">{quotes.length ? quotes.map((item, index) => {
      const quote = item.evidence || item
      const citation = evidencePages(record, item)
      return <div key={index} className="space-y-1 text-xs"><p className="break-all text-ink-faint">{quote.field_path}</p><blockquote className="whitespace-pre-wrap break-words border-l-2 border-brand/30 pl-2 leading-5">{quote.quote || 'No retained quote.'}</blockquote><div className="flex flex-wrap gap-1">{citation.pages.map(number => <button key={number} type="button" className="paper-source-link" onClick={() => setPage(number)}>p. {number}</button>)}</div>{citation.unresolved.length > 0 && <p className="text-amber-700">{citation.unresolved.length} reference(s) have no unique page link.</p>}</div>
    }) : <p className="text-xs text-ink-muted">No exact citation was retained for these values. Inspect the PDF manually.</p>}<p className="text-[11px] text-ink-faint">Quotes can span several pages. A citation locates text; it does not prove that the contract belongs to this invoice.</p></div></details>
    <footer className="shrink-0 border-t border-surface-border p-3"><button type="button" className="paper-secondary w-full !py-2 !text-xs" onClick={onClose}>Return to contract association</button></footer>
  </div>
}

/** Review deterministic suggestions and record a human association independently of source fields. */
export default function ContractAssociationReview({ pkg, onChange, api, disabled = false, lockedIdentity = null, onAgreement, saveActionLabel = 'Reconcile package' }) {
  const [query, setQuery] = useState('')
  const [request, setRequest] = useState(null)
  const [response, setResponse] = useState(null)
  const [selection, setSelection] = useState(null)
  const [resources, setResources] = useState(null)
  const [reason, setReason] = useState('')
  const [error, setError] = useState('')
  const [sourceSelection, setSourceSelection] = useState(null)
  const dialog = useRef(null)
  const returnTarget = useRef(null)
  const lastSource = useRef(Symbol('initial'))
  const sourceId = pkg.invoice.source_document_id
  const canSearch = typeof sourceId === 'string' && Boolean(sourceId.trim()) && sourceId.trim().length <= 128
  const fingerprint = associationFingerprint(pkg)
  useEffect(() => {
    if (lastSource.current === sourceId) return
    lastSource.current = sourceId
    setRequest(canSearch ? { pkg, fingerprint: associationFingerprint(pkg), offset: 0, search: '' } : null)
    setQuery(''); setSelection(null); setReason(''); setSourceSelection(null)
  }, [pkg, sourceId, canSearch])
  useEffect(() => {
    if (!request) return
    let active = true
    api.associationCandidates({ invoice: request.pkg.invoice, review_context: request.pkg.review_context ?? null, offset: request.offset, limit: 25, search: request.search || null })
      .then(data => { if (active) setResponse({ request, api, data }) })
      .catch(err => { if (active) setResponse({ request, api, error: formatError(err) }) })
    return () => { active = false }
  }, [api, request])
  useEffect(() => {
    if (!selection) return
    let active = true
    loadAssociationResources(api, selection.candidate, selection.pkg).then(data => { if (active) setResources({ selection, api, data }) })
    return () => { active = false }
  }, [api, selection])
  const loaded = !request || response?.request === request && response?.api === api
  const current = Boolean(request && loaded && request.fingerprint === fingerprint)
  const data = request && loaded ? response.data : null
  const resourcesReady = resources?.selection === selection && resources?.api === api
  const exact = resourcesReady ? resources.data.agreement : null
  const candidate = selection?.candidate
  const selectionCurrent = current && selection?.request === request && selection?.fingerprint === fingerprint
  const sourceData = resourcesReady ? resources.data.sources : []
  const contractIds = [...new Set(exact?.draft.source_document_ids || [])]
  const invoiceIds = [sourceId].filter(Boolean)
  const confirmed = Boolean(pkg.association)
  useEffect(() => {
    if (selectionCurrent && exact) onAgreement?.(exact)
  }, [selectionCurrent, exact, onAgreement])
  const refresh = (offset = 0) => {
    if (!canSearch) return
    setError(''); setSelection(null); setResources(null); setSourceSelection(null); setReason('')
    setRequest({ pkg, fingerprint, offset, search: query.trim() })
  }
  const choose = next => {
    setError(''); setSourceSelection(null)
    if (!sameReference(candidate, next)) onAgreement?.(null)
    setReason(sameReference(pkg.association, next) ? pkg.association.reason || '' : '')
    setSelection({ candidate: next, pkg, request, fingerprint })
  }
  const confirm = () => {
    try {
      if (!selectionCurrent || !exact) throw new Error('Refresh the candidates and inspect the selected approved contract before confirming.')
      onChange(confirmAssociation(pkg, candidate, reason, lockedIdentity))
      onAgreement?.(exact)
      setError('')
    } catch (err) { setError(formatError(err)) }
  }
  const closeSource = () => {
    dialog.current?.close()
    setSourceSelection(null)
    requestAnimationFrame(() => returnTarget.current?.isConnected && returnTarget.current.focus({ preventScroll: true }))
  }
  const inspect = next => {
    returnTarget.current = next.returnTarget
    setSourceSelection(next)
  }
  useEffect(() => {
    if (sourceSelection && resourcesReady && dialog.current && !dialog.current.open) dialog.current.showModal()
  }, [sourceSelection, resourcesReady])
  const trapFocus = event => {
    if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); closeSource() }
    if (event.key === 'Tab') {
      const controls = [...dialog.current.querySelectorAll('button:not(:disabled), a[href], input, select, summary')].filter(node => node.getClientRects().length)
      const first = controls[0]; const last = controls[controls.length - 1]
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
    }
  }
  return <section className="paper-panel min-w-0 space-y-4 p-4" aria-label="Contract association review">
    <header className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="font-semibold">Contract association</h3><p className="mt-1 text-xs leading-5 text-ink-muted">Find an approved contract, inspect its source evidence, then confirm which version belongs to this invoice.</p></div><span className={`paper-comparison-result ${confirmed ? 'is-reported' : 'is-review'}`}>{confirmed ? 'Confirmation ready to save' : 'Confirmation needed'}</span></header>
    <div className="grid gap-3 md:grid-cols-2"><div className="rounded-lg bg-surface-muted p-3"><h4 className="mb-2 text-xs font-semibold">Invoice source fields</h4><dl className="grid grid-cols-1 gap-2 sm:grid-cols-3">{IDENTITY.map(key => <div key={key}><dt className="text-[11px] text-ink-muted">{LABELS[key]}</dt><dd className="mt-1 break-words text-xs">{shown(pkg.invoice.fields?.[key])}</dd></div>)}</dl><p className="mt-2 text-[11px] leading-4 text-ink-faint">Original invoice values stay separate from the assigned master IDs.</p></div><div className="rounded-lg border border-surface-border p-3"><h4 className="mb-2 text-xs font-semibold">Assigned master IDs {confirmed ? `· contract v${pkg.association.version_number}` : '· unconfirmed'}</h4><dl className="grid grid-cols-1 gap-2 sm:grid-cols-3">{IDENTITY.map(key => <div key={key}><dt className="text-[11px] text-ink-muted">{LABELS[key]}</dt><dd className="mt-1 break-words text-xs">{shown(pkg.identity?.[key])}</dd></div>)}</dl></div></div>
    {confirmed && <div className="paper-notice space-y-2"><p className="text-xs"><Check size={13} className="mr-1 inline" />Contract v{pkg.association.version_number} selected. {pkg.association.reason}</p><p className="text-[11px] leading-4">Select {saveActionLabel} to save the association with your identity and time. Editing invoice fields or allocation requires confirmation again.</p><button type="button" className="paper-text-action text-xs" disabled={disabled} onClick={() => onChange({ ...pkg, association: null })}>Clear association confirmation</button></div>}
    {lockedIdentity && <p className="text-xs leading-5 text-ink-muted">This existing case keeps its assigned identity. Candidates with another identity can be inspected but require a new invoice case.</p>}
    <div className="flex flex-wrap items-end gap-2"><label className="min-w-0 flex-1 text-xs font-medium text-ink-muted">Search approved contracts<input className="paper-input mt-1" value={query} maxLength={200} placeholder="Contract number, supplier, or property" disabled={disabled} onChange={event => setQuery(event.target.value)} onKeyDown={event => { if (event.key === 'Enter') { event.preventDefault(); refresh() } }} /></label><button type="button" className="paper-secondary" disabled={disabled || !canSearch || !loaded && Boolean(request)} onClick={() => refresh()}><RefreshCw size={14} />{query.trim() ? 'Search contracts' : 'Refresh suggestions'}</button></div>
    {!canSearch && <p className="paper-notice text-xs" role="status">Start from an uploaded invoice, or enter its source document ID under Rent invoice → Document references and additional attributes. Contract suggestions become available once a source is supplied.</p>}
    {!loaded && <p role="status" className="paper-loading !text-xs"><RefreshCw size={14} className="animate-spin" />Scanning a batch of approved contract versions…</p>}
    {request && loaded && response.error && <p className="paper-error" role="alert">{response.error} <button type="button" className="paper-text-action" onClick={() => refresh()}>Retry contract search</button></p>}
    {request && loaded && !current && <p className="paper-notice" role="status">The invoice or reviewed allocation changed. Refresh suggestions before selecting or confirming a contract.</p>}
    {data && <>
      <p role="status" className="text-xs leading-5 text-ink-muted">{data.state === 'ambiguous' ? 'Several contracts may fit. Compare the evidence and confirm the correct one.' : data.state === 'no_match' ? data.has_more ? 'No relevant match in this batch. More approved contracts remain to scan.' : 'No relevant match in the scanned batch. Inspect approved candidates manually or change the search.' : 'Suggested contracts use source references and coverage. Every association requires your confirmation.'} {data.has_more && 'This batch is not the whole repository.'}</p>
      {data.history_incomplete ? <p className="paper-notice text-xs" role="status">The approved history scan reached its configured limit. Older approved versions may be missing from these suggestions; review the agreement master when the expected contract is absent.</p> : !data.exhaustive && <p className="text-xs leading-5 text-ink-muted">This result covers a batch of approved versions. Absence from this list does not establish that no contract exists in the repository.</p>}
      <div className="grid max-h-80 gap-2 overflow-auto sm:grid-cols-2">{data.candidates.map(item => <button key={`${item.agreement_id}-${item.version_number}`} type="button" className={`rounded-xl border p-3 text-left ${sameReference(candidate, item) ? 'border-brand bg-brand/5' : 'border-surface-border hover:bg-surface-muted'}`} disabled={disabled || !current} aria-pressed={sameReference(candidate, item)} onClick={() => choose(item)}><span className="flex items-start justify-between gap-2"><strong className="break-words text-sm">{item.identity.contract_number}</strong><span className="shrink-0 text-[11px] text-ink-faint">v{item.version_number}</span></span><span className="mt-1 block break-words text-xs text-ink-muted">{item.vendor_name || item.identity.vendor_id} · {item.location || item.identity.store_id}</span><span className="mt-2 block text-[11px] text-ink-muted">{item.effective_from} → {item.effective_to}</span><span className="mt-2 block text-xs font-medium">{item.relevant ? 'Suggested by source references' : 'Approved candidate · manual inspection'} · {item.coverage === 'verified' ? 'Coverage verified' : item.coverage === 'conflicting' ? 'Coverage conflicts' : 'Coverage unverified'}</span>{!candidateAllowed(item, lockedIdentity) && <span className="mt-1 block text-[11px] text-amber-700">{lockedIdentity && !IDENTITY.every(key => lockedIdentity[key] === item.identity[key]) ? 'Different case identity' : 'Not eligible for confirmation'}</span>}</button>)}</div>
      {!data.candidates.length && <p className="rounded-lg bg-surface-muted p-3 text-sm text-ink-muted">No approved candidates returned. Search another batch, review the agreement master, or adjust the search.</p>}
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs"><button type="button" className="paper-secondary" disabled={disabled || !current || !request.offset} onClick={() => refresh(Math.max(0, request.offset - 25))}>Previous batch</button><span className="text-ink-faint">Batch {Math.floor(request.offset / 25) + 1} · policy {data.policy_id} v{data.policy_version}</span><button type="button" className="paper-secondary" disabled={disabled || !current || !data.has_more} onClick={() => refresh(data.next_offset ?? request.offset + 25)}>Next batch</button></div>
    </>}
    {candidate && selectionCurrent && <div className="space-y-4 border-t border-surface-border pt-4"><div><h4 className="text-sm font-semibold">Review contract {candidate.identity.contract_number} · v{candidate.version_number}</h4><p className="mt-1 text-xs text-ink-muted">Confirm the supplier, property, references, and coverage in both PDFs. Similar amounts do not establish a link.</p></div>
      {!resourcesReady && <p role="status" className="paper-loading !text-xs">Loading the exact approved contract and source evidence…</p>}
      {resourcesReady && resources.data.error && <p className="paper-error" role="alert">{resources.data.error} <button type="button" className="paper-text-action" onClick={() => setSelection({ ...selection })}>Retry sources</button></p>}
      <div className="overflow-x-auto rounded-lg border border-surface-border"><table className="paper-comparison-table paper-association-table"><thead><tr><th scope="col">Association signal</th><th scope="col">Invoice source</th><th scope="col">Approved contract</th><th scope="col">Suggestion result</th></tr></thead><tbody>{(candidate.signals || []).map((signal, index) => <tr key={`${signal.field}-${index}`}><th scope="row">{signal.label}</th><td><p className="whitespace-pre-wrap break-words text-xs">{shown(signal.invoice_value)}</p>{resourcesReady && <SourceButtons side="invoice" signal={signal} sources={sourceData} ids={invoiceIds} evidence={pkg.invoice.evidence || []} onInspect={inspect} />}</td><td><p className="whitespace-pre-wrap break-words text-xs">{shown(signal.contract_value)}</p>{resourcesReady && <SourceButtons side="contract" signal={signal} sources={sourceData} ids={contractIds} evidence={exact?.draft.evidence || []} onInspect={inspect} />}</td><td><SignalResult signal={signal} /><p className="mt-1 text-[11px] text-ink-faint">{signal.strength === 'exact' ? 'Exact identifier' : signal.strength === 'supporting' ? 'Supporting clue' : 'Coverage context'}</p></td></tr>)}</tbody></table></div>
      {resourcesReady && sourceData.some(item => item.error) && <div className="paper-notice space-y-2 text-xs"><p>Some original PDFs could not be loaded. Inspect your original files independently before confirming. Candidate values remain available.</p><button type="button" className="paper-text-action" onClick={() => setSelection({ ...selection })}>Retry source documents</button></div>}
      <label className="block text-xs font-medium text-ink-muted">Reason for confirming this contract<textarea className="paper-input mt-1" rows={2} value={reason} maxLength={2000} disabled={disabled || !selectionCurrent} placeholder="Explain which supplier, property, reference, or period evidence establishes this association." onChange={event => setReason(event.target.value)} /></label>
      <button type="button" className="paper-primary" disabled={disabled || !selectionCurrent || !exact || !candidateAllowed(candidate, lockedIdentity) || !reason.trim()} onClick={confirm}><Check size={14} />Confirm contract association</button>
      <p className="text-[11px] leading-4 text-ink-faint">Confirmation assigns master IDs separately. It does not fill missing invoice fields or approve payment. Reconciliation and AP approval remain separate steps.</p>
    </div>}
    {error && <p className="paper-error" role="alert">{error}</p>}
    {sourceSelection && resourcesReady && selectionCurrent && <dialog ref={dialog} className="paper-panel paper-association-dialog" style={{ width: 'calc(100vw - 2rem)', maxWidth: '1100px', maxHeight: '90dvh', padding: 0, overflow: 'hidden' }} aria-label="Contract association source review" onCancel={event => { event.preventDefault(); closeSource() }} onKeyDown={trapFocus}><AssociationSource api={api} selection={sourceSelection} sources={sourceData} agreement={exact} invoice={pkg.invoice} onSelect={setSourceSelection} onClose={closeSource} /></dialog>}
  </section>
}
