import { useCallback, useEffect, useRef, useState } from 'react'
import { ArrowRight, ClipboardCheck, FileCheck2, Files, HelpCircle, Receipt, RefreshCw, Settings2 } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import { usePaperApi } from '../hooks/usePaperApi'
import { formatError } from '../paper/helpers'
import AgreementWorkspace from '../components/paper/AgreementWorkspace'
import InvoiceWorkspace from '../components/paper/InvoiceWorkspace'
import ExtractionPanel from '../components/paper/ExtractionPanel'
import './Paper.css'

const STAGES = [
  { id: 'documents', label: 'Documents', detail: 'Upload & inspect', icon: Files },
  { id: 'agreements', label: 'Agreement master', detail: 'Repository & approvals', icon: FileCheck2 },
  { id: 'invoices', label: 'Invoices', detail: 'Reconcile & decide', icon: Receipt },
]

export default function Paper() {
  const paperApi = usePaperApi()
  const [searchParams] = useSearchParams()
  const [tab, setTab] = useState('documents')
  const [schemas, setSchemas] = useState([])
  const [context, setContext] = useState(null)
  const [agreement, setAgreement] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [extraction, setExtraction] = useState(null)
  const stageButtons = useRef({})
  const stageContent = useRef(null)
  const previousInitialJob = useRef(searchParams.get('extraction'))
  const draftRequest = useRef(0)
  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [catalog, review] = await Promise.all([paperApi.getSchemas(), paperApi.reviewContext()])
      setSchemas(catalog)
      setContext(review)
    } catch (err) { setError(formatError(err)) }
    finally { setLoading(false) }
  }, [paperApi])
  useEffect(() => { load() }, [load])
  useEffect(() => {
    const job = searchParams.get('extraction')
    if (job && job !== previousInitialJob.current) setTab('documents')
    previousInitialJob.current = job
  }, [searchParams])
  useEffect(() => {
    document.title = 'PAPER review — Intelidoc'
    return () => { document.title = 'Intelidoc' }
  }, [])

  function switchStage(id, focus = false) {
    setTab(id)
    if (focus) stageButtons.current[id]?.focus()
  }

  function navigateStage(event, index) {
    const destination = event.key === 'Home' ? 0 : event.key === 'End' ? STAGES.length - 1 : event.key === 'ArrowRight' ? (index + 1) % STAGES.length : event.key === 'ArrowLeft' ? (index + STAGES.length - 1) % STAGES.length : null
    if (destination === null) return
    event.preventDefault()
    switchStage(STAGES[destination].id, true)
  }

  function continueToStage(id) {
    switchStage(id)
    requestAnimationFrame(() => {
      stageContent.current?.focus({ preventScroll: true })
      stageContent.current?.scrollIntoView({ block: 'start', behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' })
    })
  }

  return (
    <div className="paper-workspace mx-auto max-w-[1600px] space-y-5">
      <header className="paper-workspace-header flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="paper-eyebrow mb-2 flex items-center gap-2"><ClipboardCheck size={15} /> PAPER</div>
          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Document review</h1>
          <p className="mt-2 max-w-2xl text-sm text-ink-muted">Inspect the source, approve agreement terms, then reconcile your invoices.</p>
        </div>
        <div className="paper-workspace-tools flex flex-wrap gap-2">
          <details className="paper-header-disclosure">
            <summary><HelpCircle size={15} /> How it works</summary>
            <div className="paper-header-popover space-y-3">
              <strong className="block text-sm text-ink">From document to decision</strong>
              <ol className="space-y-3 text-xs leading-5 text-ink-muted">
                <li><strong className="block text-ink">1. Review and edit extracted fields</strong>Upload a PDF or open a saved result. Select Review / edit to correct fields beside the original.</li>
                <li><strong className="block text-ink">2. Save to the agreement master</strong>Select Save draft version to add the agreement to the Rent Agreement Master Repository. Review the saved version and its accounting classification before approval.</li>
                <li><strong className="block text-ink">3. Reconcile the invoice</strong>Use the approved terms, add supporting documents, and review findings before recording the AP decision.</li>
              </ol>
              <p className="border-t border-surface-border pt-3 text-xs leading-5 text-ink-muted">Uploads and saved versions stay in history. Draft edits stay local until saved. AP approval records review; payment and SAP posting are separate steps.</p>
            </div>
          </details>
          <details className="paper-header-disclosure">
            <summary aria-label="Workspace details"><Settings2 size={15} /><span className="hidden sm:inline">Workspace</span></summary>
            <div className="paper-header-popover space-y-3">
              <strong className="block text-sm text-ink">Workspace details</strong>
              {context && <dl className="space-y-2 text-xs text-ink-muted"><div><dt>Reviewer</dt><dd className="break-all font-medium text-ink">{context.user_id}</dd></div><div><dt>Access</dt><dd>{context.can_decide_cases ? 'Prepare & review invoices' : 'Read & prepare invoices'}{context.can_approve_agreements ? ' · Approve agreements' : ''}</dd></div><div><dt>Reconciliation policy</dt><dd className="break-all">{context.policy_id} · v{context.policy_version}</dd></div></dl>}
              <button className="paper-secondary w-full" onClick={load} disabled={loading}><RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Refresh access</button>
            </div>
          </details>
        </div>
      </header>
      {error && <div role="alert" className="paper-error">{error} <button className="underline" onClick={load}>Retry</button></div>}
      {loading && <div role="status" className="paper-loading"><RefreshCw size={16} className="animate-spin" /> {context ? 'Refreshing workspace access…' : 'Preparing your workspace…'}</div>}
      {context && <>
        <div role="tablist" aria-label="PAPER stages" className="paper-stage-tabs">
          {STAGES.map(({ id, label, detail, icon: Icon }, index) => <button key={id} id={`paper-tab-${id}`} ref={element => { stageButtons.current[id] = element }} role="tab" aria-selected={tab === id} aria-controls={`paper-panel-${id}`} tabIndex={tab === id ? 0 : -1} className="paper-stage-button" onClick={() => switchStage(id)} onKeyDown={event => navigateStage(event, index)}>
            <span className="paper-stage-icon" aria-hidden="true"><Icon size={18} /></span>
            <span className="min-w-0"><span className="paper-stage-label">{label}</span><span className="paper-stage-detail">{detail}</span></span>
            <span className="paper-stage-number" aria-hidden="true">0{index + 1}</span>
          </button>)}
        </div>
        <div ref={stageContent} tabIndex={-1} className="paper-stage-content">
          <div role="tabpanel" id="paper-panel-documents" aria-labelledby="paper-tab-documents" hidden={tab !== 'documents'} className={tab === 'documents' ? 'paper-enter' : ''}>
            <ExtractionPanel initialJobId={searchParams.get('extraction')} onPrepareDraft={record => { setExtraction({ ...record, draft_request_id: ++draftRequest.current }); continueToStage(record.schema_name.includes('agreement') ? 'agreements' : 'invoices') }} />
            <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-ink-muted"><span>Already have the details?</span><button className="paper-text-action" onClick={() => continueToStage('agreements')}>Create an agreement <ArrowRight size={13} /></button><button className="paper-text-action" onClick={() => continueToStage('invoices')}>Build an invoice package <ArrowRight size={13} /></button></div>
          </div>
          <div role="tabpanel" id="paper-panel-agreements" aria-labelledby="paper-tab-agreements" hidden={tab !== 'agreements'} className={tab === 'agreements' ? 'paper-enter' : ''}><AgreementWorkspace schemas={schemas} context={context} extraction={extraction?.schema_name.includes('agreement') ? extraction : null} onSaved={setAgreement} onUseForInvoice={(version) => { setAgreement(version); continueToStage('invoices') }} /></div>
          <div role="tabpanel" id="paper-panel-invoices" aria-labelledby="paper-tab-invoices" hidden={tab !== 'invoices'} className={tab === 'invoices' ? 'paper-enter' : ''}><InvoiceWorkspace schemas={schemas} context={context} agreement={agreement} extraction={extraction?.schema_name.includes('invoice') ? extraction : null} /></div>
        </div>
      </>}
    </div>
  )
}
