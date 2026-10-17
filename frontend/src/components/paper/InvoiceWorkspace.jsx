import { useCallback, useContext, useEffect, useRef, useState } from 'react'
import { Plus, RefreshCw, ArrowLeft, FileText } from 'lucide-react'
import { usePaperApi } from '../../hooks/usePaperApi'
import { formatError, formatStatus, sameIdentity, schemaByName } from '../../paper/helpers'
import InvoicePaymentReview, { INVOICE_PAYMENT_FIELDS } from './InvoicePaymentReview'
import { reviewEligibility, replacePackage, applyPackageIdentity } from '../../paper/caseReview'
import SchemaFields, { revealInvalidField } from './SchemaFields'
import JsonImport from './JsonImport'
import SourceReview from './SourceReview'
import { FieldSourceContext } from './FieldSourceLinks'
import { sourceForDraft } from '../../paper/sourceReview'
import { invoiceFromExtraction } from '../../paper/extractionDraft'

const ROLES = [
  { key: 'tax_invoices', schema: 'tax_invoice', label: 'Tax invoice' },
  { key: 'utility_statements', schema: 'utility_statement', label: 'Utility statement' },
  { key: 'supporting_documents', schema: 'supporting_document', label: 'Supporting document' },
]
const PAGE_SIZE = 20
const clone = (value) => JSON.parse(JSON.stringify(value))
const blankPackage = (identity) => ({ identity: identity ? { ...identity } : { vendor_id: '', store_id: '', contract_number: '' }, invoice: { source_document_id: '', fields: {} }, tax_invoices: [], utility_statements: [], supporting_documents: [] })
const timestamp = (value) => value ? new Date(value).toLocaleString() : '—'

function Status({ value }) {
  const color = ['approved', 'matched'].includes(value) ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-300' : ['mismatched', 'rejected', 'duplicate'].includes(value) ? 'bg-red-500/10 text-red-700 dark:text-red-300' : 'bg-amber-500/10 text-amber-700 dark:text-amber-300'
  return <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${color}`}>{formatStatus(value)}</span>
}

function DocumentFields({ document, schema, label, onChange, onRemove, disabled, open = false, idPrefix, exclude = [] }) {
  const reviewSource = useContext(FieldSourceContext)
  const sourceContext = document.source_document_id && document.source_document_id === reviewSource?.record?.result?.document?.document_id ? { ...reviewSource, evidence: document.evidence || [] } : null
  const withheldCertificate = document.fields?.document_type === 'withholding_certificate'
  const displaySchema = withheldCertificate && schema?.properties?.total ? { ...schema, properties: { ...schema.properties, total: { ...schema.properties.total, title: 'Withheld amount on certificate (total)' } } } : schema
  const sourceFields = ['vendor_id', 'store_id', 'contract_number', 'extensions']
  return <FieldSourceContext.Provider value={sourceContext}><details className="paper-panel paper-disclosure min-w-0 p-4" open={open || Boolean(document.warnings?.length) || undefined}>
    <summary className="flex flex-wrap items-center justify-between gap-2"><span className="flex items-center gap-2"><FileText size={16} /> {label}</span><span className="max-w-full truncate text-xs font-normal">{document.fields?.invoice_number || 'Document fields'}{document.warnings?.length ? ` · ${document.warnings.length} warnings` : ''}</span></summary>
    <div className="mt-4 space-y-4">
      {!!document.warnings?.length && <div className="space-y-2" aria-label={`${label} extraction warnings`}>{document.warnings.map((warning, index) => <p key={index} className="paper-notice break-words">{typeof warning === 'string' ? warning : warning.message || warning.code || 'Review this extraction warning.'}</p>)}</div>}
      <details className="paper-disclosure" open={!document.source_document_id && !disabled || undefined}><summary className="text-xs text-ink-muted">Document references and additional attributes</summary><div className="mt-3 space-y-4">
      <label className="block text-xs font-medium text-ink-muted">Source document ID<input className="paper-input mt-1" value={document.source_document_id || ''} disabled={disabled} required onChange={(event) => onChange({ ...document, source_document_id: event.target.value })} /></label>
      <SchemaFields schema={displaySchema} value={document.fields || {}} disabled={disabled} idPrefix={idPrefix} only={sourceFields.filter(field => !exclude.includes(field))} onChange={(fields) => onChange({ ...document, fields })} />
      </div></details>
      {withheldCertificate && <p className="paper-notice">Enter fields verified from the actual withholding certificate. Its total is the withheld amount, not gross rent or net payable. Reference, date, invoice identity, currency, and amount are checked.</p>}
      <SchemaFields schema={displaySchema} value={document.fields || {}} disabled={disabled} idPrefix={idPrefix} exclude={[...exclude, ...sourceFields]} onChange={(fields) => onChange({ ...document, fields })} />
      <details className="paper-disclosure text-xs text-ink-muted"><summary>Technical evidence and source metadata · {document.evidence?.length || 0} citations</summary><pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap break-all rounded-lg bg-surface-muted p-3 text-xs">{JSON.stringify({ evidence: document.evidence || [], warnings: document.warnings || [], content_sha256: document.content_sha256 || null }, null, 2)}</pre></details>
      {onRemove && <button type="button" className="paper-secondary" disabled={disabled} onClick={onRemove}>Remove {label.toLowerCase()}</button>}
    </div>
  </details></FieldSourceContext.Provider>
}

export default function InvoiceWorkspace({ schemas, context, agreement, extraction }) {
  const paperApi = usePaperApi()
  const [cases, setCases] = useState([])
  const [offset, setOffset] = useState(0)
  const [listLoading, setListLoading] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [versions, setVersions] = useState([])
  const [historyOffset, setHistoryOffset] = useState(0)
  const [latest, setLatest] = useState(0)
  const [selected, setSelected] = useState(null)
  const [editor, setEditor] = useState(null)
  const [reason, setReason] = useState('')
  const [overrides, setOverrides] = useState([])
  const [pendingExtraction, setPendingExtraction] = useState(null)
  const [editorSource, setEditorSource] = useState(null)
  const selectionRequest = useRef(0)
  const listRequest = useRef(0)
  const handledExtraction = useRef(null)

  const loadCases = useCallback(async () => {
    const request = ++listRequest.current
    setListLoading(true)
    try {
      const records = await paperApi.listCases({ limit: PAGE_SIZE, offset })
      if (request === listRequest.current) setCases(records)
    }
    catch (err) { if (request === listRequest.current) setError(formatError(err)) }
    finally { if (request === listRequest.current) setListLoading(false) }
  }, [offset, paperApi])
  useEffect(() => { loadCases() }, [loadCases])
  const loadExtractedDraft = useCallback((record) => {
    try {
      const pkg = invoiceFromExtraction(record)
      selectionRequest.current += 1
      setSelected(null); setVersions([]); setLatest(0); setReason(''); setOverrides([])
      setEditor({ package: pkg, case_id: null }); setError(''); setPendingExtraction(null)
      setEditorSource(record)
      setNotice('Review and edit the invoice below, add supporting documents, then select Reconcile package to save and assess it. Source evidence and warnings remain attached. Supply missing identifiers and service dates from verified sources.')
    } catch (err) { setError(formatError(err)) }
  }, [])
  useEffect(() => {
    const request = extraction?.draft_request_id ?? extraction
    if (!extraction || busy || handledExtraction.current === request) return
    handledExtraction.current = request
    if (editor) setPendingExtraction(extraction)
    else loadExtractedDraft(extraction)
  }, [extraction, editor, busy, loadExtractedDraft])
  const openCase = async (record) => {
    const request = ++selectionRequest.current
    setBusy(true); setError(''); setNotice(''); setEditor(null); setReason(''); setOverrides([])
    try {
      const history = await paperApi.caseVersions(record.case_id, { limit: PAGE_SIZE, offset: 0 })
      if (request !== selectionRequest.current) return
      setVersions(history); setSelected(history[0]); setLatest(history[0]?.version_number || record.version_number); setHistoryOffset(0)
    } catch (err) { if (request === selectionRequest.current) setError(formatError(err)) }
    finally { if (request === selectionRequest.current) setBusy(false) }
  }
  const newPackage = () => {
    selectionRequest.current += 1
    setSelected(null); setVersions([]); setLatest(0); setReason(''); setOverrides([]); setError(''); setNotice('')
    setEditor({ package: blankPackage(agreement?.identity), case_id: null })
    setEditorSource(null)
  }
  const save = async (event) => {
    event.preventDefault()
    setBusy(true); setError(''); setNotice('')
    try {
      const record = editor.case_id ? await paperApi.reviseCase(editor.case_id, { expected_version: editor.expected_version, package: editor.package }) : await paperApi.createCase(editor.package)
      setSelected(record); setLatest(record.version_number); setEditor(null); setReason(''); setOverrides([]); setHistoryOffset(0)
      setVersions(await paperApi.caseVersions(record.case_id, { limit: PAGE_SIZE, offset: 0 }))
      setNotice(`Version ${record.version_number} saved and assessed. ${formatStatus(record.status)}.`)
      await loadCases()
    } catch (err) { setError(`${formatError(err)}${err.status === 409 ? ' Refresh the latest version before retrying.' : ''}`) }
    finally { setBusy(false) }
  }
  const decide = async (action) => {
    setBusy(true); setError(''); setNotice('')
    try {
      const record = await paperApi.decideCase(selected.case_id, selected.version_number, { action, reason: reason.trim(), override_codes: action === 'approve' ? overrides : [] })
      setSelected(record); setVersions((old) => old.map((item) => item.version_number === record.version_number ? record : item)); setReason(''); setOverrides([])
      setNotice(`AP ${action === 'approve' ? 'approval' : 'rejection'} recorded for version ${record.version_number}.`)
      await loadCases()
    } catch (err) { setError(`${formatError(err)}${err.status === 409 ? ' Refresh the latest version and reassess before retrying.' : ''}`) }
    finally { setBusy(false) }
  }
  const pageHistory = async (nextOffset) => {
    setBusy(true); setError('')
    try {
      const history = await paperApi.caseVersions(selected.case_id, { limit: PAGE_SIZE, offset: nextOffset })
      setVersions(history)
      setHistoryOffset(nextOffset)
      if (!nextOffset) setLatest(history[0]?.version_number || 0)
      setSelected((current) => history.find((record) => record.version_number === current?.version_number) || current)
    }
    catch (err) { setError(formatError(err)) }
    finally { setBusy(false) }
  }
  const patchPackage = (changes) => setEditor((current) => ({ ...current, package: { ...current.package, ...changes } }))
  const addWithholdingCertificate = () => {
    patchPackage({ supporting_documents: [...(editor.package.supporting_documents || []), { source_document_id: '', fields: { document_type: 'withholding_certificate' }, evidence: [], warnings: [] }] })
    setNotice('Blank withholding certificate added. Supply the actual document ID and source-verified reference, date, identities, currency, and withheld amount. This action creates no source evidence or tax document.')
  }
  const eligibility = reviewEligibility(selected, latest, context, overrides)
  const shownPackage = editor?.package || selected?.package
  const reviewSource = editor ? sourceForDraft(editorSource, [editor.package.invoice.source_document_id]) : null
  const matchedAgreement = agreement && sameIdentity(agreement.identity, shownPackage?.identity) ? agreement : null
  const reference = selected?.assessment?.agreement_reference
  const readAgreement = matchedAgreement && reference?.agreement_id === matchedAgreement.agreement_id && reference.version_number === matchedAgreement.version_number ? matchedAgreement : null

  return <div className="space-y-4">
    {pendingExtraction && <div className="paper-notice space-y-3"><p><strong>{editor ? 'You have an unsaved invoice package.' : 'An extracted invoice is ready for review.'}</strong> {editor ? <>Review <strong>{pendingExtraction.filename}</strong> by replacing it, or keep your current work. Replacing discards its unsaved changes and supporting documents.</> : <>Open <strong>{pendingExtraction.filename}</strong> to review its extracted fields.</>}</p><div className="flex flex-wrap gap-2"><button type="button" className="paper-primary" disabled={busy} onClick={() => loadExtractedDraft(pendingExtraction)}>{editor ? 'Replace unsaved package and review' : 'Review extracted invoice'}</button><button type="button" className="paper-secondary" disabled={busy} onClick={() => setPendingExtraction(null)}>{editor ? 'Keep current package' : 'Dismiss'}</button></div></div>}
    <div className={`grid min-w-0 grid-cols-1 items-start gap-5 ${reviewSource ? '' : 'xl:grid-cols-[300px_minmax(0,1fr)]'}`}>
    <aside className="paper-panel min-w-0 space-y-4 p-4">
      <details open={!reviewSource} className="space-y-4"><summary>Invoice cases and saved versions</summary>
      <div className="flex items-center justify-between"><h2 className="font-semibold">Invoice cases</h2><button className="paper-secondary !p-2" aria-label="Refresh invoice cases" onClick={loadCases} disabled={listLoading || busy}><RefreshCw size={15} /></button></div>
      <button className="paper-primary w-full" onClick={newPackage} disabled={busy}><Plus size={15} /> New invoice package</button>
      {listLoading && <p role="status" className="text-xs text-ink-muted">Loading cases…</p>}
      {!listLoading && !cases.length && <p className="text-sm text-ink-muted">No cases on this page. Create an approved agreement, then assess an invoice package.</p>}
      <div className="max-h-[640px] space-y-2 overflow-auto">{cases.map((record) => <button key={record.case_id} className={`w-full rounded-xl border p-3 text-left ${selected?.case_id === record.case_id ? 'border-brand bg-brand/5' : 'border-surface-border hover:bg-surface-muted'}`} disabled={busy} onClick={() => openCase(record)}>
        <div className="mb-2 flex items-center justify-between gap-2"><span className="truncate text-sm font-semibold">{record.package.invoice.fields.invoice_number || 'Unknown invoice'}</span><span className="text-xs text-ink-faint">v{record.version_number}</span></div>
        <p className="mb-2 truncate text-xs text-ink-muted">{record.package.identity.vendor_id} · {record.package.identity.store_id}</p><Status value={record.status} />
      </button>)}</div>
      <div className="flex items-center justify-between text-xs"><button className="paper-secondary" disabled={!offset || busy || listLoading} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>Previous</button><span className="text-ink-muted">Page {offset / PAGE_SIZE + 1}</span><button className="paper-secondary" disabled={cases.length < PAGE_SIZE || busy || listLoading} onClick={() => setOffset(offset + PAGE_SIZE)}>Next</button></div>
      </details>
    </aside>
    <div className="min-w-0 space-y-4">
      {error && <div className="paper-error" role="alert">{error} {error.includes('409') && <span>Refresh the case and review its current version before retrying.</span>}</div>}
      {notice && <p className="paper-notice" role="status">{notice}</p>}
      {!shownPackage && <div className="paper-panel space-y-5 p-8"><h2 className="text-xl font-semibold">Build a document package</h2><p className="text-sm text-ink-muted">Start with a rent invoice and add tax invoices, utility statements, or supporting documents. The configured rules will show missing information and discrepancies.</p><p className="text-sm text-ink-muted">Required document roles: {context.required_documents.map(formatStatus).join(', ')}.</p><button className="paper-primary" onClick={newPackage} disabled={busy}>Create an invoice package</button></div>}
      {shownPackage && <>
        <div className="paper-panel paper-enter flex min-w-0 flex-wrap items-center justify-between gap-3 p-5"><div className="min-w-0"><h2 className="break-words text-xl font-semibold">{editor ? (editor.case_id ? 'Correct and reassess invoice' : 'Review / edit invoice') : shownPackage.invoice.fields.invoice_number || 'Invoice review'}</h2><p className="mt-1 text-xs text-ink-muted">{editor ? 'Unsaved package. Review fields, add supporting documents, then Reconcile package to save and assess. AP approval follows separately.' : `Version ${selected.version_number} · ${timestamp(selected.created_at)}`}</p>{!editor && <p className="mt-2 break-words text-xs text-ink-muted">{shownPackage.invoice.fields.vendor_name || shownPackage.identity.vendor_id} · {shownPackage.identity.store_id} · {shownPackage.identity.contract_number}</p>}</div>{selected && !editor && <Status value={selected.status} />}</div>
        {editor && <SourceReview record={reviewSource} evidence={editor.package.invoice.evidence} warnings={editor.package.invoice.warnings} fieldData={editor.package.invoice.fields} editable fieldsLabel="Editable invoice fields"><form onSubmit={save} onInvalidCapture={revealInvalidField} className="paper-enter min-w-0 space-y-4">
          <div className="paper-panel space-y-3 p-4"><div className="flex flex-wrap items-center justify-between gap-3"><h3 className="text-sm font-semibold">Agreement identity</h3>{agreement && !editor.case_id && <button type="button" className="paper-secondary text-xs" disabled={busy} onClick={() => setEditor((current) => ({ ...current, package: applyPackageIdentity(current.package, agreement.identity) }))}>Use selected agreement identity</button>}</div><div className="grid grid-cols-1 gap-3 md:grid-cols-3">{['vendor_id', 'store_id', 'contract_number'].map((field) => <label key={field} className="min-w-0 text-xs font-medium text-ink-muted">{formatStatus(field)}<input className="paper-input mt-1" value={editor.package.identity[field] || ''} required disabled={busy || Boolean(editor.case_id)} onChange={(event) => patchPackage({ identity: { ...editor.package.identity, [field]: event.target.value } })} /></label>)}</div></div>
          <InvoicePaymentReview pkg={editor.package} agreement={matchedAgreement} reviewPolicy={context} disabled={busy} onChange={pkg => setEditor(current => ({ ...current, package: pkg }))} />
          <DocumentFields document={editor.package.invoice} schema={schemaByName(schemas, 'rent_invoice')} label="Rent invoice" idPrefix="invoice-edit" open disabled={busy} exclude={INVOICE_PAYMENT_FIELDS} onChange={(invoice) => patchPackage({ invoice })} />
          {ROLES.map((role) => <div key={role.key} className="space-y-3">{(editor.package[role.key] || []).map((document, index) => <DocumentFields key={`${role.key}-${index}`} document={document} schema={schemaByName(schemas, role.schema)} label={`${role.label} ${index + 1}`} idPrefix={`${role.key}-edit-${index}`} disabled={busy} onChange={(next) => patchPackage({ [role.key]: editor.package[role.key].map((item, i) => i === index ? next : item) })} onRemove={() => patchPackage({ [role.key]: editor.package[role.key].filter((_, i) => i !== index) })} />)}<button className="paper-secondary" type="button" disabled={busy} onClick={() => patchPackage({ [role.key]: [...(editor.package[role.key] || []), { source_document_id: '', fields: {} }] })}><Plus size={14} /> Add {role.label.toLowerCase()}</button></div>)}
          <button type="button" className="paper-secondary" disabled={busy} onClick={addWithholdingCertificate}>Add withholding certificate fields</button>
          <details className="paper-panel paper-disclosure p-4"><summary className="text-sm font-medium">Advanced package import</summary><div className="mt-4 space-y-4">
          <JsonImport value={editor.package} kind="package" currentIdentity={editor.case_id ? editor.package.identity : undefined} onImport={(value) => setEditor((current) => ({ ...current, package: replacePackage(value) }))} label="Advanced package JSON" helpText="Import a typed package, including evidence and warnings. Decimal amounts are strings. Review fields before saving." disabled={busy} />
          </div></details>
          <div className="paper-card-action flex flex-wrap gap-3"><button type="submit" className="paper-primary" disabled={busy}>{busy ? 'Saving…' : editor.case_id ? 'Save correction and reassess' : 'Reconcile package'}</button><button type="button" className="paper-secondary" disabled={busy} onClick={() => setEditor(null)}>Cancel</button></div>
        </form></SourceReview>}
        {selected && !editor && <>
          <div className="paper-panel space-y-4 p-5">
            <div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="font-semibold">Reconciliation findings</h3><p className="mt-1 text-xs text-ink-muted">{selected.assessment.findings.length} findings to review</p></div><button className="paper-secondary" disabled={busy || selected.version_number !== latest} onClick={() => { setEditor({ package: clone(selected.package), case_id: selected.case_id, expected_version: selected.version_number }); setError(''); setNotice('') }}>Correct / reassess</button></div>
            {selected.duplicate_of && <div className="paper-error"><p>This package duplicates a retained case. Approval is blocked.</p><details className="mt-2 text-xs"><summary>Duplicate reference</summary><code className="mt-2 block break-all">{selected.duplicate_of}</code></details></div>}
            {selected.assessment.agreement_reference ? <div className="paper-notice"><p>Approved agreement · version {selected.assessment.agreement_reference.version_number} · {formatStatus(selected.assessment.agreement_reference.classification)}</p><details className="mt-2 text-xs"><summary>Agreement and policy reference</summary><p className="mt-2 break-all">Agreement {selected.assessment.agreement_reference.agreement_id}</p><p className="mt-1 break-all">Policy {selected.assessment.policy_id} v{selected.assessment.policy_version}</p></details></div> : <p className="paper-notice">No approved agreement reference. Review the agreement identity and invoice period, then reassess.</p>}
            {!selected.assessment.findings.length && <p className="text-sm text-emerald-700 dark:text-emerald-300">All configured checks passed.{!selected.decision && ' An authorized AP reviewer can now record a decision.'}</p>}
            <div className="space-y-2">{selected.assessment.findings.map((finding, index) => <div key={`${finding.code}-${index}`} className="rounded-lg border border-surface-border p-3"><div className="flex flex-wrap items-center gap-2"><span className="text-sm font-semibold">{formatStatus(finding.code)}</span><span className="text-xs uppercase text-ink-faint">{finding.severity}</span></div><p className="mt-1 break-words text-sm text-ink-muted">{finding.message}</p>{(finding.field_path || finding.source_document_ids?.length > 0) && <details className="mt-2 text-xs text-ink-faint"><summary>Field and source references</summary>{finding.field_path && <p className="mt-2 break-all font-mono">{finding.field_path}</p>}<p className="mt-1 break-all">{(finding.source_document_ids || []).join(', ')}</p></details>}</div>)}</div>
          </div>
          <InvoicePaymentReview pkg={selected.package} agreement={readAgreement} reviewPolicy={context} disabled />
          <div className="paper-panel space-y-4 p-5"><h3 className="font-semibold">AP decision</h3>
            {selected.decision ? <div className="space-y-2 text-sm"><Status value={selected.status} /><p>{selected.decision.reason}</p><p className="text-xs text-ink-muted">{selected.decision.decided_by} · {timestamp(selected.decision.decided_at)}</p>{selected.decision.override_codes.length > 0 && <p className="text-xs text-ink-muted">Accepted exceptions: {selected.decision.override_codes.join(', ')}</p>}</div> : <>
              {eligibility.reason && <p className="paper-notice">{eligibility.reason}</p>}
              {eligibility.codes.filter((code) => context.override_codes.includes(code)).map((code) => <label className="flex items-start gap-2 text-sm" key={code}><input type="checkbox" className="mt-1 rounded text-brand" checked={overrides.includes(code)} disabled={busy || !eligibility.canDecide} onChange={(event) => setOverrides((old) => event.target.checked ? [...old, code] : old.filter((item) => item !== code))} /><span>Accept {formatStatus(code).toLowerCase()} as a reviewed exception</span></label>)}
              <label className="block text-xs font-medium text-ink-muted">Decision reason<textarea className="paper-input mt-1" rows={3} value={reason} disabled={busy || !eligibility.canDecide} onChange={(event) => setReason(event.target.value)} placeholder="Record what you reviewed and why." /></label>
              <div className="flex flex-wrap gap-2"><button className="paper-primary" disabled={busy || !eligibility.canApprove || !reason.trim()} onClick={() => decide('approve')}>Approve invoice</button><button className="paper-secondary" disabled={busy || !eligibility.canDecide || !reason.trim()} onClick={() => decide('reject')}>Reject invoice</button></div>
              <p className="text-xs text-ink-faint">Decisions are retained in history. An AP approval records review; SAP posting is a later integration.</p>
            </>}
          </div>
          <details className="paper-panel p-5"><summary>Source document fields and evidence</summary><div className="mt-4 space-y-3"><DocumentFields document={selected.package.invoice} schema={schemaByName(schemas, 'rent_invoice')} label="Rent invoice" idPrefix="invoice-read" disabled onChange={() => {}} />{ROLES.flatMap((role) => (selected.package[role.key] || []).map((document, index) => <DocumentFields key={`${role.key}-${index}`} document={document} schema={schemaByName(schemas, role.schema)} label={`${role.label} ${index + 1}`} idPrefix={`${role.key}-read-${index}`} disabled onChange={() => {}} />))}</div></details>
          <details className="paper-panel paper-disclosure p-5"><summary className="font-semibold">Version history · current v{selected.version_number}</summary><div className="mt-4 space-y-3"><button className="paper-secondary" disabled={busy} onClick={() => openCase(selected)}><RefreshCw size={14} /> Reload latest</button><div className="flex flex-wrap gap-2">{versions.map((record) => <button key={record.version_number} className={selected.version_number === record.version_number ? 'paper-primary' : 'paper-secondary'} disabled={busy} onClick={() => { setSelected(record); setReason(''); setOverrides([]); setError(''); setNotice('') }}>v{record.version_number} · {formatStatus(record.status)}</button>)}</div><div className="flex gap-2"><button className="paper-secondary" disabled={busy || !historyOffset} onClick={() => pageHistory(Math.max(0, historyOffset - PAGE_SIZE))}><ArrowLeft size={14} /> Newer</button><button className="paper-secondary" disabled={busy || versions.length < PAGE_SIZE} onClick={() => pageHistory(historyOffset + PAGE_SIZE)}>Older</button></div></div></details>
          <details className="paper-panel paper-disclosure p-5"><summary>Advanced: audit snapshot JSON</summary><pre className="mt-3 max-h-96 overflow-auto whitespace-pre-wrap break-all text-xs">{JSON.stringify(selected, null, 2)}</pre></details>
        </>}
      </>}
    </div>
  </div></div>
}
