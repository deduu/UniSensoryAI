import { useCallback, useEffect, useRef, useState } from 'react'
import { ArrowLeft } from 'lucide-react'
import SchemaFields, { revealInvalidField } from './SchemaFields'
import SourceReview from './SourceReview'
import ContractAssociationReview from './ContractAssociationReview'
import CasePreparation from './CasePreparation'
import { schemaByName, formatError, formatStatus } from '../../paper/helpers'
import { invoiceFromExtraction } from '../../paper/extractionDraft'
import { draftSaveRequest, preparationRequest, readinessForPolicy } from '../../paper/savedDraftFlow'
import { invalidateAssociation } from '../../paper/contractAssociation'

const ROLES = ['rent_invoice', 'tax_invoice', 'utility_statement', 'supporting_document']
const clone = value => JSON.parse(JSON.stringify(value))
const blank = () => ({ source_document_id: '', fields: {}, evidence: [], warnings: [] })
const emptySelection = record => ({ invoice: { draft_id: record.draft_id, version_number: record.version_number }, tax_invoices: [], utility_statements: [], supporting_documents: [] })
const invoicePackage = record => ({ identity: { vendor_id: '', store_id: '', contract_number: '' }, invoice: clone(record.document), tax_invoices: [], utility_statements: [], supporting_documents: [], association: null })

/** Save source review independently, then explicitly assemble a case from reviewed versions. */
export default function SavedDocumentWorkspace({ api, schemas, context, openRequest, onSaved, onCaseCreated, onOpenSource, onRefreshPolicy }) {
  const [document, setDocument] = useState(blank)
  const [role, setRole] = useState('rent_invoice')
  const [record, setRecord] = useState(null)
  const [history, setHistory] = useState([])
  const [editing, setEditing] = useState(false)
  const [reviewed, setReviewed] = useState(false)
  const [reason, setReason] = useState('')
  const [source, setSource] = useState(null)
  const [sourceError, setSourceError] = useState('')
  const [sourceRetry, setSourceRetry] = useState(0)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [pending, setPending] = useState(null)
  const [phase, setPhase] = useState('review')
  const [pkg, setPackage] = useState(null)
  const [selection, setSelection] = useState(null)
  const [readiness, setReadiness] = useState(null)
  const [allocation, setAllocation] = useState(false)
  const consumed = useRef(null)
  const sequence = useRef(0)
  const mounted = useRef(false)
  const currentPreparation = useRef(0)
  useEffect(() => { mounted.current = true; return () => { mounted.current = false } }, [])
  useEffect(() => {
    currentPreparation.current += 1
    setReadiness(null)
  }, [context.policy_id, context.policy_version])
  const activeReadiness = readinessForPolicy(readiness, context)

  const startPreparation = useCallback(saved => {
    if (saved.role !== 'rent_invoice' || saved.status !== 'reviewed') throw new Error('Save a reviewed invoice version before preparing a case.')
    currentPreparation.current += 1
    setPackage(invoicePackage(saved)); setSelection(emptySelection(saved)); setReadiness(null); setAllocation(false); setPhase('prepare')
  }, [])
  const open = useCallback(async request => {
    const ticket = ++sequence.current
    setBusy(true); setError(''); setNotice(''); setPending(null)
    try {
      let saved = null, versions = [], next = blank(), nextRole = request.role || 'rent_invoice'
      if (request.record) {
        saved = await api.documentDraftVersion(request.record.draft_id, request.record.version_number)
        if (saved.draft_id !== request.record.draft_id || saved.version_number !== request.record.version_number) throw new Error('The requested saved version could not be verified.')
        const page = await api.documentDraftVersions(saved.draft_id, { limit: 100 })
        versions = page.items
        next = saved.document; nextRole = saved.role
      } else if (request.extraction) next = invoiceFromExtraction(request.extraction).invoice
      if (!mounted.current || ticket !== sequence.current) return
      currentPreparation.current += 1
      setRecord(saved); setHistory(versions); setDocument(clone(next)); setRole(nextRole); setEditing(!saved); setReviewed(false); setReason(''); setPhase('review'); setPackage(null); setSelection(null); setReadiness(null)
      setSource(request.extraction || null)
      if (request.prepare && saved) startPreparation(saved)
    } catch (failure) { if (mounted.current && ticket === sequence.current) setError(formatError(failure)) }
    finally { if (mounted.current && ticket === sequence.current) setBusy(false) }
  }, [api, startPreparation])
  useEffect(() => {
    if (!openRequest || consumed.current === openRequest.request_id || busy) return
    consumed.current = openRequest.request_id
    if (editing || phase === 'prepare') setPending(openRequest)
    else open(openRequest)
  }, [openRequest, busy, editing, phase, open])
  const sourceId = document.source_document_id
  useEffect(() => {
    let active = true
    setSourceError('')
    if (!sourceId) { setSource(null); return undefined }
    setSource(null)
    api.extractionByDocument(sourceId).then(value => { if (active) setSource(value) }).catch(() => { if (active) setSourceError('Original PDF unavailable. Saved fields and evidence remain available.') })
    return () => { active = false }
  }, [api, sourceId, sourceRetry])

  async function save(event) {
    event.preventDefault(); setBusy(true); setError(''); setNotice('')
    try {
      const payload = draftSaveRequest(record, role, document, reviewed, reason)
      const saved = record ? await api.reviseDocumentDraft(record.draft_id, payload) : await api.createDocumentDraft(payload)
      if (!mounted.current) return
      // Commit success stays visible even if the following history refresh fails.
      setRecord(saved); setDocument(clone(saved.document)); setEditing(false); setReviewed(false); setReason('')
      setNotice(`Saved ${saved.status === 'reviewed' ? 'reviewed' : 'draft'} version ${saved.version_number}. No reconciliation was run.`)
      onSaved?.(saved)
      try { const page = await api.documentDraftVersions(saved.draft_id, { limit: 100 }); if (mounted.current) setHistory(page.items) }
      catch { if (mounted.current) setNotice(`Version ${saved.version_number} was saved. Version history could not refresh; reopen the saved draft to retry.`) }
    } catch (failure) { if (mounted.current) setError(formatError(failure)) }
    finally { if (mounted.current) setBusy(false) }
  }
  function updatePackage(next) {
    currentPreparation.current += 1
    setPackage(current => invalidateAssociation(current, next)); setReadiness(null); setError('')
  }
  async function check() {
    const ticket = ++currentPreparation.current
    setBusy(true); setError(''); setReadiness(null)
    try {
      const value = await api.caseReadiness(preparationRequest({ selection, package: pkg }))
      if (mounted.current && ticket === currentPreparation.current) {
        setReadiness(value)
        if (!readinessForPolicy(value, context)) {
          setNotice('Matching requirements changed. Refreshing the policy; check readiness again before running reconciliation.')
          onRefreshPolicy?.()
        }
      }
    } catch (failure) { if (mounted.current && ticket === currentPreparation.current) setError(formatError(failure)) }
    finally { if (mounted.current) setBusy(false) }
  }
  async function run() {
    if (!activeReadiness?.ready) return
    setBusy(true); setError('')
    try {
      const saved = await api.reconcileDraftSelection(preparationRequest({ selection, package: pkg }))
      if (!mounted.current) return
      setReadiness(null); setPhase('review'); setNotice(`Case v${saved.version_number} saved. ${formatStatus(saved.status)}.`)
      onCaseCreated?.(saved)
    } catch (failure) { if (mounted.current) { setError(formatError(failure)); setReadiness(null) } }
    finally { if (mounted.current) setBusy(false) }
  }
  const required = new Set(role === 'rent_invoice' ? context.required_invoice_fields : role === 'tax_invoice' ? context.required_tax_fields : [])
  const explicit = (context.field_requirements || []).filter(item => item.role === role)
  const declarations = explicit.map(item => `${formatStatus(item.field)}: ${item.requirement}${item.reason ? ` — ${item.reason}` : ''}`)
  const defaultRequired = [...required].filter(name => !explicit.some(item => item.field === name))
  const latest = Math.max(record?.version_number || 0, ...history.map(item => item.version_number))

  return <section className="min-w-0 space-y-4" aria-label="Saved document review and case preparation">
    {pending && <div className="paper-notice space-y-3" role="status"><strong>Keep your current document or case preparation?</strong><p>Opening another item discards local changes. Saved versions remain available.</p><div className="flex flex-wrap gap-2"><button className="paper-secondary" disabled={busy} onClick={() => setPending(null)}>Keep current work</button><button className="paper-primary" disabled={busy} onClick={() => open(pending)}>Discard local changes and open</button></div></div>}
    {error && <p className="paper-error" role="alert">{error}</p>}
    {notice && <p className="paper-notice" role="status">{notice}</p>}
    {busy && <p role="status" className="paper-loading">Loading or saving selected document versions…</p>}
    <header className="paper-panel flex flex-wrap items-start justify-between gap-3 p-5"><div><p className="paper-eyebrow">{phase === 'prepare' ? '2 · Prepare case' : '1 · Review document'}</p><h2 className="mt-2 text-xl font-semibold">{phase === 'prepare' ? 'Select documents and check readiness' : `${formatStatus(role)}${record ? ` · v${record.version_number}` : ' · unsaved draft'}`}</h2><p className="mt-2 text-xs text-ink-muted">{phase === 'prepare' ? 'Choose reviewed versions, confirm their contract, then explicitly run reconciliation.' : 'Save source values independently. Missing fields can remain unknown in a draft; reviewing does not approve payment.'}</p>{record && <p className="mt-2 text-xs font-semibold">{formatStatus(record.status)} · saved by {record.created_by}</p>}</div><div className="flex flex-wrap gap-2">{phase === 'prepare' ? <button className="paper-secondary" disabled={busy} onClick={() => { currentPreparation.current += 1; setPhase('review'); setReadiness(null) }}><ArrowLeft size={14} />Back to saved document</button> : !editing && <><button className="paper-secondary" disabled={busy || record?.version_number !== latest} onClick={() => { setEditing(true); setReviewed(false); setReason('') }}>Create revision</button>{record?.status === 'reviewed' && role === 'rent_invoice' && <button className="paper-primary" disabled={busy} onClick={() => startPreparation(record)}>Prepare case</button>}</>}</div></header>
    {phase === 'review' && <>
      {sourceError && <p className="paper-notice">{sourceError} <button className="underline" onClick={() => setSourceRetry(value => value + 1)}>Retry original</button></p>}
      <SourceReview record={source} evidence={document.evidence || []} warnings={document.warnings || []} fieldData={document.fields || {}} editable={editing} fieldsLabel={editing ? 'Editable document fields' : 'Saved document fields'}>
        <form onSubmit={save} onInvalidCapture={revealInvalidField} className="min-w-0 space-y-4">
          {!record && !openRequest?.extraction && <label className="block text-xs font-medium">Document role<select className="paper-input mt-1" value={role} disabled={busy} onChange={event => { setRole(event.target.value); setDocument(blank()); setReviewed(false) }}>{ROLES.map(item => <option key={item} value={item}>{formatStatus(item)}</option>)}</select></label>}
          <details className="paper-panel paper-disclosure p-4"><summary>Field requirements · {context.policy_id} v{context.policy_version}</summary><div className="mt-3 space-y-2 text-xs text-ink-muted"><p>Required for case readiness: {defaultRequired.map(formatStatus).join(', ') || 'See explicit requirements below'}.</p>{declarations.map(item => <p key={item}>{item}</p>)}<p>Other schema fields are optional for presence. Conditional accounting and approved service-coverage rules still apply. Assigned vendor/store/contract IDs remain separate from values printed in the source.</p></div></details>
          <label className="block text-xs font-medium">Source document ID<input className="paper-input mt-1" value={sourceId || ''} required disabled={!editing || busy} onChange={event => setDocument(current => ({ ...current, source_document_id: event.target.value }))} /></label>
          <SchemaFields schema={schemaByName(schemas, role)} value={document.fields || {}} onChange={fields => setDocument(current => ({ ...current, fields }))} disabled={!editing || busy} idPrefix="saved-document" requirements={explicit} requiredFields={[...required]} />
          {editing && <div className="paper-panel space-y-4 p-4"><label className="block text-xs font-medium">Review or change reason<textarea className="paper-input mt-1" rows={2} value={reason} required disabled={busy} onChange={event => setReason(event.target.value)} /></label><label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1" checked={reviewed} disabled={busy} onChange={event => setReviewed(event.target.checked)} /><span>I reviewed this document against its original and retained the evidence, warnings and unknown values. Save it as a reviewed version for case selection.</span></label><div className="flex flex-wrap gap-2"><button type="submit" className="paper-primary" disabled={busy}>{reviewed ? 'Save reviewed version' : 'Save document draft'}</button>{record && <button type="button" className="paper-secondary" disabled={busy} onClick={() => { setDocument(clone(record.document)); setEditing(false); setReviewed(false); setReason('') }}>Cancel changes</button>}</div></div>}
        </form>
      </SourceReview>
      {record && <details className="paper-panel paper-disclosure p-4"><summary>Document version history</summary><div className="mt-3 flex flex-wrap gap-2">{history.map(item => <button key={item.version_number} className={item.version_number === record.version_number ? 'paper-primary' : 'paper-secondary'} disabled={busy || editing} onClick={() => open({ record: item })}>v{item.version_number} · {formatStatus(item.status)}</button>)}</div><p className="mt-3 text-xs text-ink-muted">Corrections append a version. A previously reviewed version and any case that used it remain unchanged.</p></details>}
    </>}
    {phase === 'prepare' && pkg && <>
      <ContractAssociationReview pkg={pkg} api={api} disabled={busy} onChange={updatePackage} saveActionLabel="Run reconciliation" />
      <details className="paper-panel paper-disclosure p-4"><summary>Service allocation for an advance installment</summary><p className="mt-3 text-xs text-ink-muted">Use only an explicitly reviewed allocation supported by the contract. Source service dates remain unchanged; the backend validates approved installment rules and coverage.</p><label className="mt-3 flex items-start gap-2 text-sm"><input type="checkbox" checked={allocation} disabled={busy} onChange={event => { setAllocation(event.target.checked); updatePackage({ ...pkg, review_context: event.target.checked ? { allocation_start: '', allocation_end: '', reason: '', source_document_ids: [pkg.invoice.source_document_id] } : null }) }} />Provide a reviewed allocation</label>{allocation && <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">{['allocation_start', 'allocation_end', 'reason'].map(name => <label key={name} className={`text-xs ${name === 'reason' ? 'sm:col-span-2' : ''}`}>{formatStatus(name)}<input type={name === 'reason' ? 'text' : 'date'} className="paper-input mt-1" value={pkg.review_context?.[name] || ''} disabled={busy} onChange={event => updatePackage({ ...pkg, review_context: { ...pkg.review_context, [name]: event.target.value } })} /></label>)}<p className="text-xs text-ink-muted sm:col-span-2">Linked source: selected invoice. Contract and installment evidence remain required by the reconciliation rules.</p></div>}</details>
      <CasePreparation api={api} package={pkg} selection={selection} onSelectionChange={value => { currentPreparation.current += 1; setSelection(value); setReadiness(null) }} onPackageChange={updatePackage} readiness={activeReadiness} onCheck={check} onRun={run} disabled={busy} onOpenSource={onOpenSource} />
    </>}
  </section>
}
