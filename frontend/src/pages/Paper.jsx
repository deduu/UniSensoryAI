import { useCallback, useEffect, useRef, useState } from 'react'
import { ArrowLeft, ClipboardCheck, FileCheck2, Files, HelpCircle, Receipt, RefreshCw, Settings2 } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import { usePaperApi } from '../hooks/usePaperApi'
import { useAuth } from '../context/AuthContext'
import { useApp } from '../context/AppContext'
import { jobScope } from '../jobs/history'
import { formatError } from '../paper/helpers'
import AgreementWorkspace from '../components/paper/AgreementWorkspace'
import InvoiceWorkspace from '../components/paper/InvoiceWorkspace'
import ExtractionPanel from '../components/paper/ExtractionPanel'
import WorkspaceIndex from '../components/paper/WorkspaceIndex'
import DocumentDraftLibrary from '../components/paper/DocumentDraftLibrary'
import SavedDocumentWorkspace from '../components/paper/SavedDocumentWorkspace'
import FieldRequirementSettings from '../components/paper/FieldRequirementSettings'
import './Paper.css'

const STAGES = [
  { id: 'invoices', label: 'Cases', detail: 'Review & reconcile', icon: Receipt },
  { id: 'documents', label: 'Document inbox', detail: 'Upload & continue', icon: Files },
  { id: 'agreements', label: 'Contracts', detail: 'Master & linked invoices', icon: FileCheck2 },
  { id: 'settings', label: 'Settings', detail: 'Document match fields', icon: Settings2 },
]

/** Reset local workspace state only when the authenticated account or server changes. */
export default function Paper() {
  const { user } = useAuth()
  const { backendUrl } = useApp()
  return <PaperWorkspace key={jobScope(user, backendUrl) || JSON.stringify([backendUrl, null])} />
}

function PaperWorkspace() {
  const paperApi = usePaperApi()
  const [searchParams] = useSearchParams()
  const initialJobId = searchParams.get('extraction')
  const [tab, setTab] = useState(initialJobId ? 'documents' : 'invoices')
  const [schemas, setSchemas] = useState([])
  const [context, setContext] = useState(null)
  const [agreement, setAgreement] = useState(null)
  const [caseRecord, setCaseRecord] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [sourceLoading, setSourceLoading] = useState(false)
  const [extraction, setExtraction] = useState(null)
  const [caseRequest, setCaseRequest] = useState(null)
  const [agreementRequest, setAgreementRequest] = useState(null)
  const [documentRequest, setDocumentRequest] = useState(null)
  const [selectedExtraction, setSelectedExtraction] = useState(null)
  const [workflowDocument, setWorkflowDocument] = useState(null)
  const [workflowError, setWorkflowError] = useState('')
  const [refreshKey, setRefreshKey] = useState(0)
  const [agreementFilter, setAgreementFilter] = useState(null)
  const [caseView, setCaseView] = useState('invoice')
  const [caseBrowsing, setCaseBrowsing] = useState(false)
  const [caseListOpen, setCaseListOpen] = useState(true)
  const [contractListOpen, setContractListOpen] = useState(true)
  const [documentListOpen, setDocumentListOpen] = useState(true)
  const [draftRequest, setDraftRequest] = useState(null)
  const [draftVisible, setDraftVisible] = useState(false)
  const [draftListOpen, setDraftListOpen] = useState(true)
  const [settingsOpened, setSettingsOpened] = useState(false)
  const stageButtons = useRef({})
  const stageContent = useRef(null)
  const requestSequence = useRef(0)
  const loadSequence = useRef(0)
  const sourceSequence = useRef(0)
  const mounted = useRef(false)
  const documentStatus = useRef(null)
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; loadSequence.current += 1; sourceSequence.current += 1 } }, [])

  const load = useCallback(async () => {
    const sequence = ++loadSequence.current
    setLoading(true); setError('')
    try {
      const [catalog, review] = await Promise.all([paperApi.getSchemas(), paperApi.reviewContext()])
      if (mounted.current && sequence === loadSequence.current) { setSchemas(catalog); setContext(review) }
    } catch (err) { if (mounted.current && sequence === loadSequence.current) setError(formatError(err)) }
    finally { if (mounted.current && sequence === loadSequence.current) setLoading(false) }
  }, [paperApi])
  useEffect(() => { load() }, [load])
  useEffect(() => {
    const refresh = () => { if (document.visibilityState === 'visible') load() }
    window.addEventListener('focus', refresh)
    return () => window.removeEventListener('focus', refresh)
  }, [load])
  useEffect(() => {
    if (initialJobId) {
      setDocumentRequest({ job_id: initialJobId, request_id: ++requestSequence.current })
      setTab('documents'); setDocumentListOpen(false)
    }
  }, [initialJobId])
  useEffect(() => {
    document.title = 'PAPER cases — Intelidoc'
    return () => { document.title = 'Intelidoc' }
  }, [])

  const refreshIndexes = useCallback(() => setRefreshKey(value => value + 1), [])
  const selectExtraction = useCallback(record => {
    const previous = documentStatus.current
    if (record && previous?.id === record.job_id && previous.status !== record.status) setRefreshKey(value => value + 1)
    if (record) documentStatus.current = { id: record.job_id, status: record.status }
    setSelectedExtraction(record)
  }, [])
  const selectedJobId = selectedExtraction?.job_id
  const selectedJobStatus = selectedExtraction?.status
  useEffect(() => {
    let active = true
    setWorkflowDocument(null); setWorkflowError('')
    if (selectedJobId) paperApi.workspaceDocuments({ job_id: selectedJobId, limit: 1 }).then(page => {
      if (active) setWorkflowDocument(page.items.find(item => item.job_id === selectedJobId) || null)
    }).catch(err => { if (active) setWorkflowError(formatError(err)) })
    return () => { active = false }
  }, [paperApi, selectedJobId, selectedJobStatus, selectedExtraction, refreshKey])

  function switchStage(id, focus = false) {
    sourceSequence.current += 1
    setSourceLoading(false)
    setTab(id)
    if (id === 'settings') setSettingsOpened(true)
    if (focus) stageButtons.current[id]?.focus()
  }
  function navigateStage(event, index) {
    const destination = event.key === 'Home' ? 0 : event.key === 'End' ? STAGES.length - 1 : event.key === 'ArrowRight' ? (index + 1) % STAGES.length : event.key === 'ArrowLeft' ? (index + STAGES.length - 1) % STAGES.length : null
    if (destination === null) return
    event.preventDefault(); switchStage(STAGES[destination].id, true)
  }
  function continueToStage(id) {
    switchStage(id)
    requestAnimationFrame(() => {
      stageContent.current?.focus({ preventScroll: true })
      stageContent.current?.scrollIntoView({ block: 'start', behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' })
    })
  }
  function openCase(record) {
    setCaseRequest({ case_id: record.case_id, version_number: record.version_number, request_id: ++requestSequence.current })
    setCaseView('invoice'); setCaseBrowsing(false); setCaseListOpen(false); continueToStage('invoices')
  }
  function openContract(record, fromCase = false) {
    setAgreementRequest({ agreement_id: record.agreement_id, version_number: record.version_number, request_id: ++requestSequence.current })
    if (fromCase) { setCaseView('contract'); setCaseBrowsing(false); continueToStage('invoices') }
    else { setContractListOpen(false); continueToStage('agreements') }
  }
  function openDocument(record) {
    setDraftVisible(false)
    setDocumentRequest({ job_id: record.job_id, request_id: ++requestSequence.current })
    setDocumentListOpen(false); continueToStage('documents')
  }
  async function openSource(documentId) {
    if (!documentId) { setError('No original document reference is recorded for this item.'); return }
    const sequence = ++sourceSequence.current
    setSourceLoading(true); setError('')
    try {
      const record = await paperApi.extractionByDocument(documentId)
      if (mounted.current && sequence === sourceSequence.current) openDocument(record)
    } catch (err) { if (mounted.current && sequence === sourceSequence.current) setError(`Original PDF unavailable: ${formatError(err)}`) }
    finally { if (mounted.current && sequence === sourceSequence.current) setSourceLoading(false) }
  }
  function viewLinkedCases(record) {
    setAgreementFilter({ agreement_id: record.agreement_id, contract_number: record.identity.contract_number })
    setCaseListOpen(true); setCaseBrowsing(true); setCaseView('invoice'); continueToStage('invoices')
  }
  function openWorkflowLink(document, link) {
    if (link.kind === 'agreement') openContract({ agreement_id: link.id, version_number: link.version_number })
    else openCase({ case_id: link.id, version_number: link.version_number })
  }
  function prepareDraft(record) {
    if (record.schema_name.includes('invoice')) {
      openSavedDocument({ extraction: record })
      return
    }
    setExtraction({ ...record, draft_request_id: ++requestSequence.current })
    if (record.schema_name.includes('agreement')) { setContractListOpen(false); continueToStage('agreements') }
    else { setCaseListOpen(false); setCaseBrowsing(false); setCaseView('invoice'); continueToStage('invoices') }
  }
  function openSavedDocument(request) {
    setDraftRequest({ ...request, request_id: ++requestSequence.current })
    setDraftVisible(true); setDraftListOpen(false); setDocumentListOpen(false); continueToStage('documents')
  }
  const showAgreement = tab === 'agreements' || tab === 'invoices' && !caseBrowsing && caseView === 'contract'

  function applyFieldSettings(saved) {
    setContext(current => current && ({ ...current, policy_id: saved.policy_id, policy_version: saved.policy_version, field_requirements: saved.requirements }))
    load()
  }

  return <div className="paper-workspace mx-auto max-w-[1600px] space-y-5">
    <header className="paper-workspace-header flex flex-wrap items-start justify-between gap-4">
      <div><div className="paper-eyebrow mb-2 flex items-center gap-2"><ClipboardCheck size={15} /> PAPER</div><h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Review and reconciliation</h1><p className="mt-2 max-w-2xl text-sm text-ink-muted">Open an invoice case to review its contract, source documents and matching results together.</p></div>
      <div className="paper-workspace-tools flex flex-wrap gap-2">
        <details className="paper-header-disclosure"><summary><HelpCircle size={15} /> How it works</summary><div className="paper-header-popover space-y-3"><strong className="block text-sm text-ink">From upload to invoice decision</strong><ol className="space-y-3 text-xs leading-5 text-ink-muted"><li><strong className="block text-ink">1. Review and save documents</strong>Review extracted fields beside each PDF. Save invoice and supporting document drafts independently, then explicitly save reviewed versions for case selection. Missing values stay visible.</li><li><strong className="block text-ink">2. Approve the contract master</strong>Save the reviewed agreement as a draft version, then approve its terms. Contracts lists each master and its linked invoice cases.</li><li><strong className="block text-ink">3. Prepare the invoice case</strong>Choose Prepare case on a reviewed invoice. Confirm its exact contract, select reviewed supporting documents, and check the required, conditional and optional fields. Run reconciliation when prerequisites are ready.</li><li><strong className="block text-ink">4. Resolve and decide</strong>Compare contract expectations with invoice values, correct findings and reassess. An authorized reviewer records the AP decision separately.</li></ol><p className="border-t border-surface-border pt-3 text-xs leading-5 text-ink-muted">Saving a document or checking readiness does not create a case. Explicit reconciliation saves matching results. Uploads, evidence and version history remain available.</p></div></details>
        <details className="paper-header-disclosure"><summary aria-label="Workspace details"><Settings2 size={15} /><span className="hidden sm:inline">Workspace</span></summary><div className="paper-header-popover space-y-3"><strong className="block text-sm text-ink">Workspace details</strong>{context && <dl className="space-y-2 text-xs text-ink-muted"><div><dt>Reviewer</dt><dd className="break-all font-medium text-ink">{context.user_id}</dd></div><div><dt>Access</dt><dd>{context.can_decide_cases ? 'Prepare & review invoices' : 'Read & prepare invoices'}{context.can_approve_agreements ? ' · Approve agreements' : ''}</dd></div><div><dt>Reconciliation policy</dt><dd className="break-all">{context.policy_id} · v{context.policy_version}</dd></div></dl>}<button className="paper-secondary w-full" onClick={load} disabled={loading}><RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Refresh access</button></div></details>
      </div>
    </header>
    {error && <div role="alert" className="paper-error">{error} <button className="underline" onClick={() => setError('')}>Dismiss</button></div>}
    {(loading || sourceLoading) && <div role="status" className="paper-loading"><RefreshCw size={16} className="animate-spin" /> {sourceLoading ? 'Opening original document…' : 'Preparing workspace access…'}</div>}
    {!context && error && <button className="paper-secondary" onClick={load}>Retry workspace access</button>}
    {context && <>
      <div role="tablist" aria-label="PAPER workspace" className="paper-stage-tabs">{STAGES.map(({ id, label, detail, icon: Icon }, index) => <button key={id} id={`paper-tab-${id}`} ref={element => { stageButtons.current[id] = element }} role="tab" aria-selected={tab === id} aria-controls={`paper-panel-${id}`} tabIndex={tab === id ? 0 : -1} className="paper-stage-button" onClick={() => switchStage(id)} onKeyDown={event => navigateStage(event, index)}><span className="paper-stage-icon" aria-hidden="true"><Icon size={18} /></span><span className="min-w-0"><span className="paper-stage-label">{label}</span><span className="paper-stage-detail">{detail}</span></span></button>)}</div>
      <div ref={stageContent} tabIndex={-1} className="paper-stage-content space-y-4">
        <div role="tabpanel" id="paper-panel-invoices" aria-labelledby="paper-tab-invoices" hidden={tab !== 'invoices'} className="space-y-4">
          <details className="paper-panel paper-disclosure p-4" open={caseListOpen} onToggle={event => setCaseListOpen(event.currentTarget.open)}><summary>Find an invoice case{caseRecord && !caseListOpen ? ` · reviewing ${caseRecord.package.invoice.fields.invoice_number || 'saved case'}` : ''}</summary><div className="mt-4"><WorkspaceIndex mode="cases" api={paperApi} active={tab === 'invoices'} refreshKey={refreshKey} agreementFilter={agreementFilter} onClearAgreementFilter={() => setAgreementFilter(null)} onOpenCase={openCase} /></div></details>
          {caseBrowsing && <div className="paper-empty"><h2 className="font-semibold">Invoices linked to contract {agreementFilter?.contract_number}</h2><p className="mt-2 text-sm text-ink-muted">Select a case above to continue its review. Existing local work stays available.</p><button className="paper-secondary mt-3" onClick={() => { setCaseBrowsing(false); setCaseListOpen(false) }}>Return to current invoice workspace</button></div>}
          {!caseBrowsing && caseView === 'contract' && <div className="paper-case-context"><div><p className="paper-eyebrow">Contract review inside case</p><p className="mt-1 text-sm font-medium">{caseRecord?.package.invoice.fields.invoice_number || 'Invoice case'}</p><p className="mt-1 text-xs text-ink-muted">Review the exact linked version. Returning keeps invoice edits and history available.</p></div><button className="paper-secondary" onClick={() => setCaseView('invoice')}><ArrowLeft size={14} /> Back to invoice and matching</button></div>}
          <div hidden={caseBrowsing || caseView !== 'invoice'}><InvoiceWorkspace embedded schemas={schemas} context={context} agreement={agreement} extraction={extraction?.schema_name.includes('invoice') ? extraction : null} openRequest={caseRequest} onSelectionChange={setCaseRecord} onSaved={refreshIndexes} onOpenContract={record => openContract(record, true)} onOpenSource={openSource} onNewInvoice={() => { setDraftVisible(false); setDraftListOpen(true); continueToStage('documents') }} /></div>
        </div>
        <div role="tabpanel" id="paper-panel-documents" aria-labelledby="paper-tab-documents" hidden={tab !== 'documents'} className="space-y-4">
          {draftRequest && !draftVisible && <button className="paper-secondary" onClick={() => setDraftVisible(true)}><ArrowLeft size={13} />Return to document review and case preparation</button>}
          <details className="paper-panel paper-disclosure p-4" open={draftListOpen} onToggle={event => setDraftListOpen(event.currentTarget.open)}><summary>Saved document drafts and reviewed versions</summary><div className="mt-4 space-y-4"><div className="flex flex-wrap items-center justify-between gap-3"><p className="text-xs text-ink-muted">Review and save documents first. Prepare a case from a reviewed invoice and choose the documents to reconcile.</p><button className="paper-secondary" onClick={() => openSavedDocument({ new: true })}>New document draft</button></div><DocumentDraftLibrary api={paperApi} active={tab === 'documents'} refreshKey={refreshKey} onOpen={record => openSavedDocument({ record })} onPrepare={record => openSavedDocument({ record, prepare: true })} /></div></details>
          {caseRecord && <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-ink-muted"><span>Review sources without losing your case.</span><button className="paper-text-action" onClick={() => { setCaseBrowsing(false); setCaseView('invoice'); continueToStage('invoices') }}><ArrowLeft size={13} /> Return to {caseRecord.package.invoice.fields.invoice_number || 'invoice case'}</button></div>}
          <details className="paper-panel paper-disclosure p-4" open={documentListOpen} onToggle={event => setDocumentListOpen(event.currentTarget.open)}><summary>Uploaded documents and next actions</summary><div className="mt-4"><WorkspaceIndex mode="documents" api={paperApi} active={tab === 'documents'} refreshKey={refreshKey} onOpenDocument={openDocument} onDocumentAction={openWorkflowLink} /></div></details>
          {workflowError && <div role="alert" className="paper-notice">Saved workflow links could not be loaded: {workflowError} <button className="underline" onClick={refreshIndexes}>Retry</button></div>}
          <div hidden={draftVisible}><ExtractionPanel hideHistory openRequest={documentRequest} onPrepareDraft={prepareDraft} onSelected={selectExtraction} onChanged={refreshIndexes} workflowDocument={workflowDocument} onWorkflowAction={openWorkflowLink} /></div>
          <div hidden={!draftVisible}>{draftRequest && <SavedDocumentWorkspace api={paperApi} schemas={schemas} context={context} openRequest={draftRequest} onSaved={refreshIndexes} onCaseCreated={record => { refreshIndexes(); openCase(record) }} onOpenSource={openSource} onRefreshPolicy={load} />}</div>
        </div>
        <div role="tabpanel" id="paper-panel-agreements" aria-labelledby="paper-tab-agreements" hidden={tab !== 'agreements'} className="space-y-4">
          <details className="paper-panel paper-disclosure p-4" open={contractListOpen} onToggle={event => setContractListOpen(event.currentTarget.open)}><summary>Rent Agreement Master Repository</summary><div className="mt-4"><WorkspaceIndex mode="contracts" api={paperApi} active={tab === 'agreements'} refreshKey={refreshKey} onOpenContract={record => openContract(record)} onViewInvoices={viewLinkedCases} /></div></details>
        </div>
        <div role="tabpanel" id="paper-panel-settings" aria-labelledby="paper-tab-settings" hidden={tab !== 'settings'} className="space-y-4">
          {settingsOpened && <FieldRequirementSettings api={paperApi} schemas={schemas} onSaved={applyFieldSettings} />}
        </div>
        <div hidden={!showAgreement} role="region" aria-label="Contract review workspace"><AgreementWorkspace embedded schemas={schemas} context={context} extraction={extraction?.schema_name.includes('agreement') ? extraction : null} openRequest={agreementRequest} onSelectionChange={setAgreement} onSaved={record => { setAgreement(record); refreshIndexes() }} onUseForInvoice={viewLinkedCases} onViewInvoices={viewLinkedCases} onOpenSource={openSource} /></div>
      </div>
    </>}
  </div>
}
