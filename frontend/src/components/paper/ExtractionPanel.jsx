import { useCallback, useEffect, useRef, useState } from 'react'
import { Archive, ArchiveRestore, Download, FileUp, History, RefreshCw } from 'lucide-react'
import { usePaperApi } from '../../hooks/usePaperApi'
import { canPrepareDraft, extractionWarnings } from '../../paper/extractionDraft'
import { formatError, formatStatus } from '../../paper/helpers'
import SourceReview, { ExtractedFields } from './SourceReview'
import AgreementPartyRoles from './AgreementPartyRoles'
import ExtractionUsage from './ExtractionUsage'
import { modelDescription, modelLabel } from '../../jobs/presentation'
import { DocumentWorkflowActions } from './WorkspaceIndex'

const PAGE_SIZE = 10
const active = record => ['pending', 'processing', 'queued'].includes(record?.status)
const time = value => value ? new Date(value).toLocaleString() : '—'
const schemaLabel = name => name?.includes('agreement') ? 'Agreement' : 'Invoice'

function download(value, filename, type) {
  const url = URL.createObjectURL(new Blob([value], { type }))
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

/** Durable, provider-neutral extraction history with an explicit draft handoff. */
export default function ExtractionPanel({ onPrepareDraft, initialJobId, openRequest, hideHistory = false, onSelected, onChanged, workflowDocument, onWorkflowAction }) {
  const paperApi = usePaperApi()
  const [schema, setSchema] = useState('rent_agreement')
  const [mode, setMode] = useState('text')
  const [file, setFile] = useState(null)
  const [records, setRecords] = useState([])
  const [offset, setOffset] = useState(0)
  const [archived, setArchived] = useState(false)
  const [selected, setSelected] = useState(null)
  const [loading, setLoading] = useState(false)
  const [detailLoading, setDetailLoading] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const mounted = useRef(false)
  const listRequest = useRef(0)
  const detailRequest = useRef(0)
  const input = useRef(null)

  useEffect(() => { mounted.current = true; return () => { mounted.current = false } }, [])

  const load = useCallback(async (quiet = false, pageOffset = offset, includeArchived = archived) => {
    const request = ++listRequest.current
    if (!quiet) setLoading(true)
    try {
      const page = await paperApi.listExtractions({ limit: PAGE_SIZE, offset: pageOffset, archived: includeArchived })
      if (mounted.current && listRequest.current === request) {
        setRecords(page)
        setError('')
      }
    } catch (err) {
      if (mounted.current && listRequest.current === request) setError(formatError(err))
    } finally {
      if (mounted.current && listRequest.current === request) setLoading(false)
    }
  }, [offset, archived, paperApi])

  useEffect(() => { if (!hideHistory) load() }, [load, hideHistory])
  useEffect(() => { onSelected?.(selected) }, [selected, onSelected])

  const open = useCallback(async (id, quiet = false) => {
    const request = ++detailRequest.current
    if (!quiet) { setDetailLoading(true); setSelected(null) }
    try {
      const record = await paperApi.getExtraction(id)
      if (mounted.current && detailRequest.current === request) setSelected(record)
    } catch (err) {
      if (mounted.current && detailRequest.current === request) setError(formatError(err))
    } finally {
      if (mounted.current && detailRequest.current === request) setDetailLoading(false)
    }
  }, [paperApi])

  useEffect(() => { if (initialJobId) open(initialJobId) }, [initialJobId, open])
  useEffect(() => { if (openRequest?.job_id) open(openRequest.job_id) }, [openRequest, open])

  useEffect(() => {
    if (!records.some(active) && !active(selected)) return undefined
    const timer = setTimeout(async () => {
      const selection = detailRequest.current
      await load(true)
      if (active(selected) && selection === detailRequest.current) await open(selected.job_id, true)
    }, 3000)
    return () => clearTimeout(timer)
  }, [records, selected, load, open])

  async function upload(event) {
    event.preventDefault()
    if (!file || busy) return
    if (!file.name.toLowerCase().endsWith('.pdf') || !file.size) { setError('Choose a nonempty PDF file.'); return }
    setBusy(true); setError(''); setNotice('')
    try {
      const record = await paperApi.uploadExtraction(file, schema, mode)
      if (!mounted.current) return
      setFile(null)
      if (input.current) input.current.value = ''
      setNotice('Upload saved. Extraction will continue in the background; reopen it from Recent uploads at any time.')
      setArchived(false)
      setOffset(0)
      await open(record.job_id)
      await load(true, 0, false)
      onChanged?.()
    } catch (err) { if (mounted.current) setError(formatError(err)) }
    finally { if (mounted.current) setBusy(false) }
  }

  async function retry() {
    if (!selected || busy) return
    setBusy(true); setError('')
    try {
      const record = await paperApi.retryExtraction(selected.job_id)
      if (!mounted.current) return
      setNotice('Retry queued. Both attempts remain in Recent uploads.')
      setArchived(false)
      setOffset(0)
      await open(record.job_id)
      await load(true, 0, false)
      onChanged?.()
    } catch (err) { if (mounted.current) setError(formatError(err)) }
    finally { if (mounted.current) setBusy(false) }
  }

  async function changeArchive() {
    if (!selected || active(selected) || busy) return
    const id = selected.job_id
    const next = !selected.archived
    setBusy(true); setError('')
    try {
      const updated = await paperApi.archiveExtractions([id], next)
      if (!mounted.current) return
      setSelected(current => current?.job_id === id ? { ...current, ...updated[0], result: current.result } : current)
      setNotice(next ? 'Attempt archived. Saved agreement versions and their original PDF evidence are retained. Restore it from Archived attempts.' : 'Attempt restored to Recent uploads.')
      setOffset(0)
      await load(true, 0)
      onChanged?.()
    } catch (err) { if (mounted.current) setError(formatError(err)) }
    finally { if (mounted.current) setBusy(false) }
  }

  const result = selected?.result
  const warnings = extractionWarnings(selected)

  return <section className="paper-panel paper-enter min-w-0 space-y-5 p-4 sm:p-5" aria-label="PDF extraction and upload history">
    <div><p className="paper-eyebrow">Start with a document</p><h2 className="mt-1 flex items-center gap-2 text-lg font-semibold"><FileUp size={20} aria-hidden="true" /> Upload a PDF</h2><p className="mt-1 text-sm text-ink-muted">Extract an agreement or invoice, then review it beside the original.</p></div>
    <form onSubmit={upload} className="min-w-0" aria-busy={busy}>
      <div className="paper-upload-controls">
        <label className="min-w-0 text-xs font-medium text-ink-muted">PDF file<input ref={input} type="file" accept=".pdf,application/pdf" required disabled={busy} className="paper-input mt-1 text-sm file:mr-3 file:rounded file:border-0 file:bg-surface-muted file:px-2 file:py-1 file:text-ink" onChange={event => { setFile(event.target.files?.[0] || null); setError('') }} /></label>
        <label className="min-w-0 text-xs font-medium text-ink-muted">Document type<select className="paper-input mt-1" value={schema} disabled={busy} onChange={event => setSchema(event.target.value)}><option value="rent_agreement">Rent agreement</option><option value="rent_invoice">Rent invoice</option></select></label>
        <details className="paper-disclosure paper-upload-options">
          <summary className="text-xs text-ink-muted"><span>Extraction options<span className="mt-1 block text-xs font-normal">{mode === 'text' ? 'Text with OCR' : 'Text and visual content'}</span></span></summary>
          <div className="paper-upload-options-content">
            <label className="min-w-0 text-xs font-medium text-ink-muted">Document content<select className="paper-input mt-1" value={mode} disabled={busy} onChange={event => setMode(event.target.value)}><option value="text">Text with OCR</option><option value="multimodal">Text and visual content</option></select></label>
            <p className="mt-2 text-xs text-ink-muted">Scanned pages use OCR. Include visual content when images or layout matter.</p>
          </div>
        </details>
        <button type="submit" className="paper-primary paper-upload-submit" disabled={busy || !file}>{busy && <RefreshCw size={14} className="animate-spin" aria-hidden="true" />}{busy ? 'Uploading…' : 'Upload and extract'}</button>
      </div>
    </form>
    {error && <p role="alert" className="paper-error">{error}</p>}
    {notice && <p role="status" className="paper-notice">{notice}</p>}
    <div className="min-w-0 space-y-4">
      {!hideHistory && <details className="paper-disclosure min-w-0 space-y-3" open={!result?.document}>
        <summary className="text-sm font-semibold">{archived ? 'Archived attempts' : 'Recent uploads'} {records.length > 0 && <span className="ml-1 text-xs font-normal text-ink-muted">({records.length}{records.length === PAGE_SIZE ? '+' : ''})</span>}</summary>
        <div className="flex flex-wrap items-center justify-between gap-2"><h3 className="flex items-center gap-2 text-xs text-ink-muted"><History size={14} aria-hidden="true" /> Saved extraction attempts</h3><div className="flex flex-wrap gap-2"><button type="button" className="paper-secondary !text-xs" aria-pressed={archived} disabled={busy} onClick={() => { setArchived(value => !value); setOffset(0) }}>{archived ? 'Show recent uploads' : 'Show archived attempts'}</button><button type="button" className="paper-secondary !p-2" aria-label="Refresh extraction history" disabled={loading} onClick={() => load()}><RefreshCw size={15} className={loading ? 'animate-spin' : ''} /></button></div></div>
        {loading && <p role="status" className="text-xs text-ink-muted">Loading saved uploads…</p>}
        {!loading && !records.length && <p className="paper-empty text-sm text-ink-muted">{archived ? 'No archived attempts. Archiving keeps saved versions and source evidence available.' : 'Your uploaded PDFs and extraction attempts will appear here.'}</p>}
        <ul className="paper-upload-history">{records.map(record => <li className="min-w-0" key={record.job_id}><button type="button" aria-pressed={selected?.job_id === record.job_id} onClick={() => open(record.job_id)} className={`paper-card-action h-full w-full min-w-0 rounded-lg border p-3 text-left ${selected?.job_id === record.job_id ? 'border-brand bg-brand/5' : 'border-surface-border hover:bg-surface-muted'}`}><span className="block break-words text-sm font-semibold">{record.filename}</span><span className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-ink-muted"><span className="paper-status">{active(record) && <RefreshCw size={11} className="animate-spin" aria-hidden="true" />}{formatStatus(record.status)}</span><span>{schemaLabel(record.schema_name)}{record.page_count != null ? ` · ${record.page_count} pages` : ''}</span>{record.warning_count > 0 && <span title="Retained diagnostics from this extraction attempt. Open Document Review for current issues and history." className="text-ink-faint">{record.warning_count} log entries</span>}</span><span className="mt-1.5 block text-xs text-ink-faint">{time(record.created_at)}</span></button></li>)}</ul>
        <div className="flex items-center justify-between text-xs text-ink-muted"><button type="button" className="paper-secondary" disabled={!offset || loading} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>Newer</button><span>Page {Math.floor(offset / PAGE_SIZE) + 1}</span><button type="button" className="paper-secondary" disabled={records.length < PAGE_SIZE || loading} onClick={() => setOffset(offset + PAGE_SIZE)}>Older</button></div>
      </details>}
      <div className="min-w-0 space-y-4 rounded-xl border border-surface-border p-3 sm:p-4" aria-label="Extraction result" aria-busy={detailLoading}>
        {detailLoading ? <p role="status" className="flex items-center gap-2 text-sm text-ink-muted"><RefreshCw size={15} className="animate-spin" aria-hidden="true" /> Loading extraction result…</p> : !selected ? <div className="paper-empty py-8 text-center"><FileUp size={28} className="mx-auto mb-3 text-ink-faint" aria-hidden="true" /><h3 className="text-sm font-medium">Ready for review</h3><p className="mt-1 text-sm text-ink-muted">Upload a PDF or select a recent file to see its fields and original pages.</p></div> : <div key={selected.job_id} className="paper-enter min-w-0 space-y-4">
          <div><h3 className="break-words font-semibold">{selected.filename}</h3><div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-ink-muted"><span className="paper-status">{active(selected) && <RefreshCw size={12} className="animate-spin" aria-hidden="true" />}{formatStatus(selected.status)}</span>{result?.status && <span>{formatStatus(result.status)}</span>}{warnings.length > 0 && <span title="Original extraction log; current review requirements are assessed below." className="text-ink-muted">{warnings.length} retained log entries</span>}<span>{time(selected.updated_at)}</span></div></div>
          <div className="flex flex-wrap gap-2">
            <a className="paper-secondary" href={paperApi.extractionFileUrl(selected.job_id)} target="_blank" rel="noreferrer">Open original PDF</a>
            <button type="button" className="paper-secondary" onClick={() => open(selected.job_id)}><RefreshCw size={14} /> Refresh result</button>
            {selected.status === 'failed' && <button type="button" className="paper-secondary" disabled={busy} onClick={retry}>Retry extraction</button>}
            {!active(selected) && <button type="button" className="paper-secondary" disabled={busy} onClick={changeArchive}>{selected.archived ? <ArchiveRestore size={14} /> : <Archive size={14} />}{selected.archived ? 'Restore attempt' : 'Archive attempt'}</button>}
          </div>
          {selected.archived && <p className="paper-notice">Archived attempt. Saved agreement history and original PDF evidence are retained. Restore it to return it to Recent uploads.</p>}
          {!result?.document && <ExtractionUsage usage={selected.usage || result?.usage} documentReuse={selected.document_reuse} />}
          {active(selected) && <p role="status" className="paper-notice flex items-center gap-2"><RefreshCw size={15} className="shrink-0 animate-spin" aria-hidden="true" /> {selected.status === 'processing' ? 'Extracting document' : 'Waiting for extraction'} · updates appear automatically. You can return later.</p>}
          {selected.error && <p className="paper-error">{typeof selected.error === 'string' ? selected.error : selected.error.message || 'Extraction failed. Retry after checking the host configuration.'}</p>}
          {result && !result.fields && <p className="paper-notice">No fields were extracted. Recovered text and warnings are still available.</p>}
          {workflowDocument?.job_id === selected.job_id && workflowDocument.workflow_links_resolved === false && selected.status === 'completed' && <p className="paper-notice">Saved workflow links are unavailable for this older upload. Check Cases and Contracts before preparing a new draft; the source index can be repaired from its stored extraction.</p>}
          {workflowDocument?.job_id === selected.job_id && workflowDocument.workflow_links?.length > 0 && <div className="rounded-lg border border-brand/20 bg-brand/5 p-3"><h4 className="text-sm font-semibold">Continue from a saved record</h4><p className="my-2 text-xs text-ink-muted">This source is already used by the records below. Open the saved version to continue reviewing or reconciling. Preparing another draft keeps these records unchanged.</p><DocumentWorkflowActions document={workflowDocument} onAction={onWorkflowAction} /></div>}
          {canPrepareDraft(selected) && <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-brand/5 p-3"><div><p className="text-sm font-semibold">Ready to review the extracted {schemaLabel(selected.schema_name).toLowerCase()}</p><p className="mt-1 text-xs text-ink-muted">{selected.schema_name.includes('agreement') ? 'Review / edit → Save draft version → Approve in Agreement master.' : 'Review fields → Save reviewed version → Select case documents → Check readiness → Run reconciliation.'}</p></div><button type="button" className="paper-primary shrink-0" onClick={() => { onPrepareDraft(selected); setNotice('Review workspace opened. Changes stay local until you save; existing unsaved work requires a replacement choice.') }}>Review / edit {schemaLabel(selected.schema_name).toLowerCase()}</button></div>}
          {selected.status === 'completed' && result?.document && !result.fields && <div className="space-y-2"><button type="button" className="paper-primary" onClick={() => onPrepareDraft(selected)}>Review / edit {schemaLabel(selected.schema_name).toLowerCase()}</button><p className="text-xs text-ink-muted">No fields were extracted. Opens a blank draft with this source and its warnings so you can enter verified values.</p></div>}
          {result?.document && <SourceReview record={selected} warnings={warnings}>{selected.schema_name === 'rent_agreement' && <AgreementPartyRoles terms={result.fields?.data} />}<ExtractedFields record={selected} data={result.fields?.data} onEdit={canPrepareDraft(selected) ? () => onPrepareDraft(selected) : undefined} /></SourceReview>}
          {!result?.document && warnings.length > 0 && <details className="paper-disclosure rounded-lg border border-amber-500/20 bg-amber-500/5 p-3"><summary className="text-sm font-medium">Retained extraction log ({warnings.length})</summary><ul className="mt-3 space-y-2 text-xs">{warnings.map((warning, index) => <li key={index}><strong className="break-all">{warning.code}</strong><p className="mt-1 break-words">{warning.message}</p></li>)}</ul></details>}
          <details className="paper-disclosure min-w-0 rounded-lg border border-surface-border p-3">
            <summary className="text-sm font-medium">Extraction details and downloads</summary>
            <p className="mt-3 break-all text-xs text-ink-muted">Job {selected.job_id}</p>
            <p title={modelDescription(selected)} className="mt-2 break-words text-xs text-ink-muted">Model: {modelLabel(selected)}</p>
            <p className="mt-1 text-xs text-ink-faint">{modelDescription(selected)}</p>
            <p className="mt-2 text-xs text-ink-muted">Draft edits leave this saved extraction unchanged.</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {result && <button type="button" className="paper-secondary" onClick={() => download(JSON.stringify(result, null, 2), `${selected.filename}.extraction.json`, 'application/json')}><Download size={14} /> Result JSON</button>}
              {result?.document && <button type="button" className="paper-secondary" onClick={() => download(result.document.text || '', `${selected.filename}.txt`, 'text/plain;charset=utf-8')}>Download text</button>}
            </div>
            {result?.document && <details className="paper-disclosure mt-3"><summary className="text-xs font-medium">Full extracted text ({result.document.text?.length.toLocaleString() || 0} characters)</summary><pre className="mt-3 max-h-80 overflow-auto whitespace-pre-wrap break-words rounded-lg bg-surface-muted p-3 text-xs">{result.document.text || 'No text recovered.'}</pre></details>}
          </details>
        </div>}
      </div>
    </div>
  </section>
}
