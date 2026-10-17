import { useCallback, useEffect, useRef, useState } from 'react'
import { ArrowRight, CheckCircle2, FilePlus2, History, RefreshCw } from 'lucide-react'
import Button from '../ui/Button'
import SchemaFields, { revealInvalidField } from './SchemaFields'
import JsonImport from './JsonImport'
import SourceReview from './SourceReview'
import ReviewInspector from './ReviewInspector'
import AgreementPaymentRules, { AGREEMENT_PAYMENT_FIELDS } from './AgreementPaymentRules'
import { assertSavedInstallmentIds } from '../../paper/installmentRules'
import { sourceForDraft } from '../../paper/sourceReview'
import { usePaperApi } from '../../hooks/usePaperApi'
import { parseSourceIds } from '../../paper/agreementInput'
import { agreementFromExtraction } from '../../paper/extractionDraft'
import {
  copyAgreementDraft,
  formatError,
  fieldDefinitions,
  schemaByName,
} from '../../paper/helpers'

const PAGE_SIZE = 100
const INPUT = 'mt-1 w-full rounded-lg border border-surface-border bg-surface px-3 py-2 text-sm text-ink focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand disabled:bg-surface-muted disabled:text-ink-muted'
const IDENTITY_FIELDS = [
  ['vendor_id', 'Vendor ID'],
  ['store_id', 'Store ID'],
  ['contract_number', 'Contract number'],
]

const TERM_GROUPS = [
  { label: 'Parties and premises', fields: ['vendor_name', 'location'], open: true },
  { label: 'Lease dates', fields: ['lease_start_date', 'lease_end_date', 'lease_duration_months'], open: true },
  { label: 'Rent and bank details', fields: ['rent_type', 'currency', 'fixed_rent', 'revenue_share_rate', 'minimum_guaranteed_payment', 'bank_account'], open: true },
  { label: 'Payment conditions', fields: ['payment_schedule'] },
  { label: 'Renewal and other terms', fields: ['renewal_terms', 'other_key_terms'] },
  { label: 'Identifiers found in the document', fields: ['vendor_id', 'store_id', 'contract_number'] },
]

function AgreementTerms({ schema, value, onChange, disabled = false, idPrefix, identity }) {
  const available = fieldDefinitions(schema).map(field => field.name)
  const grouped = TERM_GROUPS.flatMap(group => group.fields)
  const groups = [...TERM_GROUPS, { label: 'Additional source attributes', fields: available.filter(name => !grouped.includes(name) && !AGREEMENT_PAYMENT_FIELDS.includes(name)) }]
  const identityMismatch = IDENTITY_FIELDS.some(([key]) => value[key] && identity?.[key] && value[key] !== identity[key])
  return <div className="space-y-3">
    {identityMismatch && <p className="paper-notice">Document identifiers differ from the agreement identity. Review “Identifiers found in the document” before saving.</p>}
    {groups.filter(group => group.fields.some(name => available.includes(name))).map(group => <details key={group.label} className="paper-disclosure rounded-lg border border-surface-border p-4" open={group.open || (identityMismatch && group.fields.includes('vendor_id')) || undefined}>
      <summary className="cursor-pointer text-sm font-semibold text-ink">{group.label}</summary>
      <div className="mt-4"><SchemaFields schema={schema} value={value} onChange={onChange} disabled={disabled} idPrefix={idPrefix} only={group.fields} /></div>
    </details>)}
  </div>
}

function blankAgreement() {
  return {
    identity: { vendor_id: '', store_id: '', contract_number: '' },
    draft: {
      schema_id: 'paper.rent_agreement',
      schema_version: '1',
      terms: {},
      effective_from: '',
      effective_to: '',
      source_document_ids: [],
      evidence: [],
      extraction_warnings: [],
      change_reason: '',
    },
  }
}

function blankDecision() {
  return {
    classification: '',
    rule_set_id: '',
    rule_set_version: '',
    reason: '',
    acknowledge_extraction_warnings: false,
  }
}

function displayTime(value) {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString()
}

function VersionBadge({ version }) {
  return (
    <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${
      version.approval ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400' : 'bg-amber-500/10 text-amber-700 dark:text-amber-400'
    }`}>
      {version.approval ? 'Approved' : 'Draft'} · v{version.version_number}
    </span>
  )
}

/** Tenant-scoped agreement authoring and explicit, audited publication. */
export default function AgreementWorkspace({ schemas, context, onSaved, onUseForInvoice, extraction }) {
  const paperApi = usePaperApi()
  const [records, setRecords] = useState([])
  const [offset, setOffset] = useState(0)
  const [listLoading, setListLoading] = useState(true)
  const [listError, setListError] = useState('')
  const [selected, setSelected] = useState(null)
  const [versions, setVersions] = useState([])
  const [historyOffset, setHistoryOffset] = useState(0)
  const [latestNumber, setLatestNumber] = useState(0)
  const [detailLoading, setDetailLoading] = useState(false)
  const [editor, setEditor] = useState(null)
  const [editorMode, setEditorMode] = useState('new')
  const [revisionBase, setRevisionBase] = useState(null)
  const [sourceText, setSourceText] = useState('')
  const [decision, setDecision] = useState(blankDecision)
  const [asOf, setAsOf] = useState('')
  const [lookup, setLookup] = useState(null)
  const [lookupMessage, setLookupMessage] = useState('')
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [pendingExtraction, setPendingExtraction] = useState(null)
  const [editorSource, setEditorSource] = useState(null)
  const mounted = useRef(true)
  const handledExtraction = useRef(null)
  const listSequence = useRef(0)
  const detailSequence = useRef(0)
  const agreementSchema = schemaByName(schemas, 'rent_agreement')
  const isLatest = selected?.version_number === latestNumber

  useEffect(() => {
    mounted.current = true
    return () => { mounted.current = false }
  }, [])

  const loadList = useCallback(async (pageOffset) => {
    const sequence = ++listSequence.current
    setListLoading(true)
    setListError('')
    try {
      const page = await paperApi.listAgreements({ limit: PAGE_SIZE, offset: pageOffset })
      if (mounted.current && listSequence.current === sequence) setRecords(page)
    } catch (err) {
      if (mounted.current && listSequence.current === sequence) setListError(formatError(err))
    } finally {
      if (mounted.current && listSequence.current === sequence) setListLoading(false)
    }
  }, [paperApi])

  useEffect(() => { loadList(offset) }, [loadList, offset])
  const loadExtractedDraft = useCallback((record) => {
    try {
      const payload = agreementFromExtraction(record)
      ++detailSequence.current
      setSelected(null); setVersions([]); setLatestNumber(0); setDetailLoading(false)
      setEditorMode('new'); setRevisionBase(null); setEditor(payload)
      setEditorSource(record)
      setSourceText(payload.draft.source_document_ids.join('\n'))
      setError(''); setLookup(null); setLookupMessage(''); setPendingExtraction(null)
      setNotice('Review and edit the draft below, then select Save draft version to add it to the repository. Supply missing host identifiers and verify the effective dates. Source evidence and warnings remain attached; approval follows saving.')
    } catch (err) { setError(formatError(err)) }
  }, [])

  useEffect(() => {
    const request = extraction?.draft_request_id ?? extraction
    if (!extraction || busy || handledExtraction.current === request) return
    handledExtraction.current = request
    if (editor) setPendingExtraction(extraction)
    else loadExtractedDraft(extraction)
  }, [extraction, editor, busy, loadExtractedDraft])

  async function openAgreement(record) {
    const sequence = ++detailSequence.current
    setDetailLoading(true)
    setEditor(null)
    setSelected(null)
    setError('')
    setNotice('')
    setLookup(null)
    setLookupMessage('')
    setDecision(blankDecision())
    setHistoryOffset(0)
    try {
      const history = await paperApi.agreementVersions(record.agreement_id, { limit: PAGE_SIZE, offset: 0 })
      if (!mounted.current || detailSequence.current !== sequence) return
      setVersions(history)
      setLatestNumber(history[0]?.version_number || 0)
      setSelected(history[0] || record)
      setAsOf(history[0]?.draft.effective_from || record.draft.effective_from)
    } catch (err) {
      if (mounted.current && detailSequence.current === sequence) setError(formatError(err))
    } finally {
      if (mounted.current && detailSequence.current === sequence) setDetailLoading(false)
    }
  }

  function beginNew() {
    ++detailSequence.current
    const payload = blankAgreement()
    setSelected(null)
    setVersions([])
    setLatestNumber(0)
    setDetailLoading(false)
    setEditorMode('new')
    setRevisionBase(null)
    setEditor(payload)
    setEditorSource(null)
    setSourceText(payload.draft.source_document_ids.join('\n'))
    setError('')
    setNotice('')
    setLookup(null)
    setLookupMessage('')
  }

  function beginRevision() {
    if (!selected || !isLatest) return
    const draft = copyAgreementDraft(selected)
    draft.change_reason = ''
    setEditor({ identity: { ...selected.identity }, draft })
    setSourceText(draft.source_document_ids.join('\n'))
    setEditorMode('revision')
    setRevisionBase({ agreement_id: selected.agreement_id, version_number: selected.version_number, installment_ids: (selected.draft.terms.installment_schedule?.installments || []).map(item => item.installment_id) })
    setError('')
    setNotice('This correction creates a new draft. Earlier terms and approvals remain in the history.')
  }

  function importAgreement(payload) {
    assertSavedInstallmentIds(payload.draft.terms, editorMode === 'revision' ? revisionBase?.installment_ids : [])
    setEditor(payload)
    setSourceText(payload.draft.source_document_ids.join('\n'))
    setError('')
    setNotice('Imported terms, evidence, and warnings. Review the fields before saving.')
  }

  function updateDraft(field, value) {
    setEditor(current => ({ ...current, draft: { ...current.draft, [field]: value } }))
  }

  function mutationError(err) {
    return `${formatError(err)}${err.status === 409 ? ' Refresh the latest version before trying again. Copy your unsaved JSON before refreshing if you need to retain edits.' : ''}`
  }

  async function saveDraft(event) {
    event.preventDefault()
    if (!editor || busy) return
    setBusy('save')
    setError('')
    setNotice('')
    const draft = {
      ...editor.draft,
      source_document_ids: parseSourceIds(sourceText),
    }
    try {
      assertSavedInstallmentIds(draft.terms, editorMode === 'revision' ? revisionBase?.installment_ids : [])
      const saved = editorMode === 'revision'
        ? await paperApi.reviseAgreement(revisionBase.agreement_id, { expected_version: revisionBase.version_number, draft })
        : await paperApi.createAgreement({ identity: editor.identity, draft })
      if (!mounted.current) return
      setEditor(null)
      await openAgreement(saved)
      setNotice(`Draft v${saved.version_number} saved in the Rent Agreement Master Repository. Next, review and approve this version below before using it for invoice reconciliation.`)
      loadList(offset)
      onSaved?.(saved)
    } catch (err) {
      if (mounted.current) setError(mutationError(err))
    } finally {
      if (mounted.current) setBusy('')
    }
  }

  async function approve(event) {
    event.preventDefault()
    if (!selected || !isLatest || editor || busy || detailLoading || !context?.can_approve_agreements) return
    setBusy('approval')
    setError('')
    setNotice('')
    try {
      const approved = await paperApi.approveAgreement(selected.agreement_id, selected.version_number, decision)
      if (!mounted.current) return
      await openAgreement(approved)
      setNotice(`Agreement v${approved.version_number} approved. This exact version can now be used for reconciliation.`)
      loadList(offset)
      onSaved?.(approved)
    } catch (err) {
      if (mounted.current) setError(mutationError(err))
    } finally {
      if (mounted.current) setBusy('')
    }
  }

  async function historyPage(nextOffset) {
    if (!selected || busy) return
    const sequence = ++detailSequence.current
    setDetailLoading(true)
    setError('')
    try {
      const history = await paperApi.agreementVersions(selected.agreement_id, { limit: PAGE_SIZE, offset: nextOffset })
      if (!mounted.current || detailSequence.current !== sequence) return
      setVersions(history)
      setHistoryOffset(nextOffset)
      setSelected(current => history.find(version => version.version_number === current?.version_number) || current)
      if (nextOffset === 0) setLatestNumber(history[0]?.version_number || 0)
    } catch (err) {
      if (mounted.current && detailSequence.current === sequence) setError(formatError(err))
    } finally {
      if (mounted.current && detailSequence.current === sequence) setDetailLoading(false)
    }
  }

  async function lookupApproved(event) {
    event.preventDefault()
    if (!selected || busy) return
    setBusy('lookup')
    setLookup(null)
    setLookupMessage('')
    setError('')
    try {
      const effective = await paperApi.approvedAgreement(selected.identity, asOf)
      if (mounted.current) setLookup(effective)
    } catch (err) {
      if (mounted.current) {
        if (err.status === 404) setLookupMessage('No approved agreement is effective on this date.')
        else setError(formatError(err))
      }
    } finally {
      if (mounted.current) setBusy('')
    }
  }

  const independent = context?.require_independent_agreement_approval && selected?.created_by === context?.user_id
  const approvalAllowed = context?.can_approve_agreements && !independent && !detailLoading
  const retainedDraft = editor?.draft || selected?.draft
  const reviewSource = editor ? sourceForDraft(editorSource, editor.draft.source_document_ids) : null
  const requiredTerms = [
    ...(context?.agreement_required_fields || []),
    ...(context?.agreement_required_fields_by_rent_type?.[selected?.draft.terms.rent_type] || []),
  ]
  const missingTerms = [...new Set(requiredTerms)].filter(key => {
    const value = selected?.draft.terms[key]
    return value == null || value === '' || (typeof value === 'object' && Object.keys(value).length === 0)
  })

  return (
    <div className="min-w-0 space-y-4">
      <header className="paper-panel flex flex-wrap items-start justify-between gap-3 p-4 sm:p-5">
        <div><h2 className="text-xl font-semibold text-ink">Rent Agreement Master Repository</h2><p className="mt-1 text-sm text-ink-muted">Saved agreements, version history, and approvals for invoice reconciliation.</p><p className="mt-2 text-xs text-ink-muted">Review / edit → Save draft version → Approve agreement → Use for invoice</p></div>
        {editor ? <span className="rounded-full bg-amber-500/10 px-3 py-1.5 text-xs font-medium text-amber-700 dark:text-amber-400">Unsaved draft · local changes</span> : selected && <VersionBadge version={selected} />}
      </header>
    <div className={`grid min-w-0 grid-cols-1 gap-5 ${reviewSource ? '' : 'xl:grid-cols-[320px_minmax(0,1fr)]'}`}>
      <aside className="min-w-0 space-y-4">
        <details open={!reviewSource} className="space-y-4"><summary className="cursor-pointer text-sm font-semibold">Browse saved agreements and versions{reviewSource && <span className="ml-2 text-xs font-normal text-ink-muted">({records.length} on this page)</span>}</summary>
        <div className="rounded-xl border border-surface-border bg-surface p-4">
          <div className="flex items-center justify-between gap-2">
            <h3 className="font-semibold text-ink">Saved agreements</h3>
            <button type="button" title="Refresh agreement list" aria-label="Refresh agreement list" className="rounded-lg p-2 text-ink-muted hover:bg-surface-muted" disabled={listLoading || !!busy} onClick={() => loadList(offset)}>
              <RefreshCw size={16} className={listLoading ? 'animate-spin' : ''} />
            </button>
          </div>
          <p className="mt-1 text-xs leading-5 text-ink-muted">Latest versions in your tenant. Open an agreement to review its history.</p>
          <div className="mt-4 flex flex-wrap gap-2">
            <Button type="button" className="px-3 py-2" disabled={!!busy} onClick={() => beginNew()}><FilePlus2 size={15} />New draft</Button>
          </div>
        </div>
        {listError && <p role="alert" className="rounded-lg border border-red-500/20 bg-red-500/5 p-3 text-sm text-red-600 dark:text-red-400">{listError}</p>}
        <div className="overflow-hidden rounded-xl border border-surface-border bg-surface">
          {listLoading ? <p role="status" className="p-5 text-sm text-ink-muted">Loading agreements…</p> : records.length === 0 ? <p className="p-5 text-sm leading-6 text-ink-muted">{offset ? 'No more agreements on this page.' : 'No agreements yet. Review an uploaded agreement or start with a new draft.'}</p> : (
            <ul className="divide-y divide-surface-border">
              {records.map(record => (
                <li key={record.agreement_id}>
                  <button type="button" onClick={() => openAgreement(record)} disabled={!!busy} className={`w-full px-4 py-4 text-left transition-colors hover:bg-surface-muted disabled:opacity-60 ${selected?.agreement_id === record.agreement_id ? 'bg-brand/5' : ''}`}>
                    <span className="block break-words text-sm font-semibold text-ink">{record.identity.contract_number}</span>
                    <span className="mt-1 block break-words text-xs text-ink-muted">{record.identity.vendor_id} · {record.identity.store_id}</span>
                    <span className="mt-2 block"><VersionBadge version={record} /></span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          <div className="flex items-center justify-between border-t border-surface-border px-3 py-3 text-xs text-ink-muted">
            <button type="button" disabled={offset === 0 || listLoading || !!busy} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))} className="rounded px-2 py-1 hover:bg-surface-muted disabled:opacity-40">Previous</button>
            <span>Page {Math.floor(offset / PAGE_SIZE) + 1}</span>
            <button type="button" disabled={records.length < PAGE_SIZE || listLoading || !!busy} onClick={() => setOffset(offset + PAGE_SIZE)} className="rounded px-2 py-1 hover:bg-surface-muted disabled:opacity-40">Next</button>
          </div>
        </div>
        </details>
      </aside>

      <section className={`min-w-0 space-y-4 ${!editor && selected && retainedDraft ? 'pb-24' : ''}`} aria-label="Agreement details">
        {pendingExtraction && <div className="paper-notice space-y-3"><p><strong>{editor ? 'You have an unsaved agreement draft.' : 'An extracted agreement is ready for review.'}</strong> {editor ? <>Review <strong>{pendingExtraction.filename}</strong> by replacing the current local draft, or keep your current work. Replacing discards the unsaved changes currently open.</> : <>Open <strong>{pendingExtraction.filename}</strong> to review its extracted terms.</>}</p><div className="flex flex-wrap gap-2"><button type="button" className="paper-primary" disabled={!!busy} onClick={() => loadExtractedDraft(pendingExtraction)}>{editor ? 'Replace unsaved draft and review' : 'Review extracted agreement'}</button><button type="button" className="paper-secondary" disabled={!!busy} onClick={() => setPendingExtraction(null)}>{editor ? 'Keep current draft' : 'Dismiss'}</button></div></div>}
        {error && <div role="alert" className="rounded-lg border border-red-500/20 bg-red-500/5 p-4 text-sm text-red-600 dark:text-red-400">{error}{selected && <button type="button" disabled={!!busy} className="mt-2 block underline" onClick={() => openAgreement(selected)}>{editor ? 'Refresh latest version and discard edits' : 'Refresh latest version'}</button>}</div>}
        {notice && <p role="status" className="rounded-lg border border-brand/20 bg-brand/5 p-4 text-sm text-ink">{notice}</p>}
        {detailLoading && <p role="status" className="rounded-xl border border-surface-border bg-surface p-5 text-sm text-ink-muted">Loading version history…</p>}
        {!editor && selected && retainedDraft && <ReviewInspector evidence={retainedDraft.evidence || []} warnings={retainedDraft.extraction_warnings || []} sourceDocumentIds={retainedDraft.source_document_ids || []} />}

        {editor ? (
          <SourceReview record={reviewSource} evidence={editor.draft.evidence} warnings={editor.draft.extraction_warnings} sourceDocumentIds={editor.draft.source_document_ids} fieldData={editor.draft.terms} editable fieldsLabel="Editable agreement fields">
          <form id="paper-agreement-draft-form" onSubmit={saveDraft} onInvalidCapture={revealInvalidField} className="paper-enter min-w-0 space-y-6 rounded-xl border border-surface-border bg-surface p-4 sm:p-6">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div><h2 className="text-lg font-semibold text-ink">{editorMode === 'revision' ? `Review / edit agreement v${revisionBase.version_number}` : 'Review / edit agreement'}</h2><p className="mt-1 text-sm text-ink-muted">Unsaved draft. Review the fields and reason, then save a version to the repository.</p></div>
              <div className="flex flex-wrap gap-2"><Button type="submit" form="paper-agreement-draft-form" loading={busy === 'save'} disabled={!!busy || !agreementSchema}>Save draft version</Button><Button type="button" variant="ghost" disabled={!!busy} onClick={() => { setEditor(null); setNotice(''); setError('') }}>Cancel</Button></div>
            </div>
            <fieldset disabled={!!busy} className="space-y-5">
              <div>
                <h3 className="text-sm font-semibold text-ink">Agreement identity</h3>
                <p className="mt-1 text-xs text-ink-muted">Use the vendor, store and contract references from your system.</p>
                <div className="mt-3 grid gap-4 sm:grid-cols-3">
                  {IDENTITY_FIELDS.map(([key, label]) => (
                    <label key={key} className="text-sm text-ink-muted">{label}
                      <input className={INPUT} value={editor.identity[key] || ''} onChange={event => setEditor(current => ({ ...current, identity: { ...current.identity, [key]: event.target.value } }))} required maxLength={128} disabled={editorMode === 'revision'} />
                    </label>
                  ))}
                </div>
                {editorMode === 'revision' && <p className="mt-2 text-xs text-ink-muted">The identity is fixed for this agreement. Changes to terms become a new version.</p>}
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <label className="text-sm text-ink-muted">Effective from<input type="date" className={INPUT} value={editor.draft.effective_from} required onChange={event => updateDraft('effective_from', event.target.value)} /></label>
                <label className="text-sm text-ink-muted">Effective to<input type="date" className={INPUT} value={editor.draft.effective_to} min={editor.draft.effective_from || undefined} required onChange={event => updateDraft('effective_to', event.target.value)} /></label>
              </div>
              <div><h3 className="mb-3 text-sm font-semibold text-ink">Review agreement terms</h3><AgreementTerms schema={agreementSchema} value={editor.draft.terms} onChange={terms => updateDraft('terms', terms)} disabled={!!busy} idPrefix="agreement-edit" identity={editor.identity} /></div>
              <AgreementPaymentRules schema={agreementSchema} terms={editor.draft.terms} onChange={terms => updateDraft('terms', terms)} disabled={!!busy} savedInstallmentIds={editorMode === 'revision' ? revisionBase?.installment_ids : []} />
              <details className="paper-disclosure rounded-lg border border-surface-border p-4" open={!editor.draft.source_document_ids.length || undefined}><summary className="text-sm font-medium text-ink">Source references ({editor.draft.source_document_ids.length})</summary><div className="mt-3">
              <label className="block text-sm text-ink-muted">Source document IDs
                <textarea rows={2} className={INPUT} value={sourceText} onChange={event => { setSourceText(event.target.value); updateDraft('source_document_ids', parseSourceIds(event.target.value)) }} required placeholder="One ID per line" />
                <span className="mt-1 block text-xs">Retain the document IDs that the evidence references.</span>
              </label>
              </div></details>
              <label className="block text-sm text-ink-muted">Reason for this version<textarea rows={2} className={INPUT} value={editor.draft.change_reason} required maxLength={2000} onChange={event => updateDraft('change_reason', event.target.value)} placeholder="Describe the source or correction reviewed" /></label>
              <JsonImport value={editor} onImport={importAgreement} kind="agreement" currentIdentity={editorMode === 'revision' ? editor.identity : undefined} disabled={!!busy} label="Advanced: import agreement JSON" helpText="Paste an agreement request containing identity and draft. Evidence and extraction warnings remain attached to the draft." />
            </fieldset>
            <div className="flex flex-wrap items-center gap-3 border-t border-surface-border pt-4"><Button type="submit" loading={busy === 'save'} disabled={!!busy || !agreementSchema}>Save draft version</Button><p className="text-xs text-ink-muted">Adds a saved draft to this repository. Review and approval follow as a separate step.</p></div>
          </form>
          </SourceReview>
        ) : selected ? (
          <>
            <div className="space-y-5 rounded-xl border border-surface-border bg-surface p-5 sm:p-6">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div><h2 className="break-words text-lg font-semibold text-ink">{selected.identity.contract_number}</h2><p className="mt-1 break-words text-sm text-ink-muted">{selected.identity.vendor_id} · {selected.identity.store_id}</p><div className="mt-3"><VersionBadge version={selected} /></div></div>
                <div className="flex flex-wrap gap-2">
                  <Button type="button" variant="secondary" disabled={!!busy || detailLoading} onClick={() => openAgreement(selected)}><RefreshCw size={15} />Refresh</Button>
                  <Button type="button" variant="secondary" disabled={!isLatest || !!busy || detailLoading} onClick={beginRevision}>Create revision</Button>
                  {selected.approval && onUseForInvoice && <Button type="button" disabled={!!busy} onClick={() => onUseForInvoice(selected)}>Use for invoice<ArrowRight size={15} /></Button>}
                </div>
              </div>
              {!isLatest && <p className="rounded-lg bg-amber-500/10 p-3 text-sm text-amber-700 dark:text-amber-400">Historical version. Open the latest version to revise or approve.</p>}
              {isLatest && <p className="paper-notice">{selected.approval ? 'Approved version in the repository. Use for invoice to reconcile against these terms.' : 'Saved draft in the repository. Review and approve this version below before invoice reconciliation.'}</p>}
              <div className="grid gap-4 text-sm sm:grid-cols-2">
                <div><span className="text-ink-muted">Effective period</span><p className="mt-1 text-ink">{selected.draft.effective_from} → {selected.draft.effective_to}</p></div>
                <div><span className="text-ink-muted">Created</span><p className="mt-1 break-words text-ink">{displayTime(selected.created_at)} · {selected.created_by}</p></div>
                <div className="sm:col-span-2"><span className="text-ink-muted">Version reason</span><p className="mt-1 whitespace-pre-wrap break-words text-ink">{selected.draft.change_reason}</p></div>
              </div>
              <details className="paper-disclosure text-sm"><summary className="cursor-pointer text-ink">Advanced: exact saved version JSON</summary><pre className="mt-3 max-h-96 overflow-auto whitespace-pre-wrap break-words rounded-lg bg-surface-muted p-3 text-xs text-ink-muted">{JSON.stringify(selected, null, 2)}</pre></details>
              <AgreementTerms schema={agreementSchema} value={selected.draft.terms} disabled idPrefix={`agreement-read-${selected.version_number}`} identity={selected.identity} />
              <AgreementPaymentRules schema={agreementSchema} terms={selected.draft.terms} disabled />
              {selected.approval && (
                <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-4 text-sm">
                  <h3 className="flex items-center gap-2 font-semibold text-ink"><CheckCircle2 size={17} />Publication decision</h3>
                  <dl className="mt-3 grid gap-3 sm:grid-cols-2">
                    <div><dt className="text-ink-muted">Classification</dt><dd className="mt-1 text-ink">{selected.approval.classification === 'psak73' ? 'PSAK 73' : 'Non-PSAK 73'}</dd></div>
                    <div><dt className="text-ink-muted">Policy reference</dt><dd className="mt-1 break-words text-ink">{selected.approval.rule_set_id} · {selected.approval.rule_set_version}</dd></div>
                    <div><dt className="text-ink-muted">Approved by</dt><dd className="mt-1 break-words text-ink">{selected.approval.approved_by} · {displayTime(selected.approval.approved_at)}</dd></div>
                    <div><dt className="text-ink-muted">Warnings acknowledged</dt><dd className="mt-1 text-ink">{selected.approval.acknowledge_extraction_warnings ? 'Yes' : 'No'}</dd></div>
                    <div className="sm:col-span-2"><dt className="text-ink-muted">Review reason</dt><dd className="mt-1 whitespace-pre-wrap break-words text-ink">{selected.approval.reason}</dd></div>
                  </dl>
                </div>
              )}
            </div>

            {!selected.approval && isLatest && (
              <form onSubmit={approve} className="space-y-4 rounded-xl border border-surface-border bg-surface p-5 sm:p-6">
                <div><h3 className="font-semibold text-ink">Review and approve this version</h3><p className="mt-1 text-sm text-ink-muted">Record the classification and accounting policy that you reviewed. The backend validates completeness and authority.</p></div>
                {(!context?.can_approve_agreements || independent) && <p className="rounded-lg bg-amber-500/10 p-3 text-sm text-amber-700 dark:text-amber-400">{independent ? 'An independent reviewer must approve this version.' : 'Your account cannot approve agreements. An authorized reviewer can publish this draft.'}</p>}
                {!!missingTerms.length && <p className="rounded-lg bg-amber-500/10 p-3 text-sm text-amber-700 dark:text-amber-400">Required publication terms are missing: {missingTerms.map(key => key.replaceAll('_', ' ')).join(', ')}. Create a revision to complete these terms.</p>}
                <fieldset disabled={!approvalAllowed || !!busy} className="space-y-4">
                  <div className="grid gap-4 sm:grid-cols-3">
                    <label className="text-sm text-ink-muted">Classification<select className={INPUT} value={decision.classification} required onChange={event => setDecision(current => ({ ...current, classification: event.target.value }))}><option value="">Choose classification</option><option value="psak73">PSAK 73</option><option value="non_psak73">Non-PSAK 73</option></select></label>
                    <label className="text-sm text-ink-muted">Rule set ID<input className={INPUT} value={decision.rule_set_id} required maxLength={128} onChange={event => setDecision(current => ({ ...current, rule_set_id: event.target.value }))} /></label>
                    <label className="text-sm text-ink-muted">Rule set version<input className={INPUT} value={decision.rule_set_version} required maxLength={128} onChange={event => setDecision(current => ({ ...current, rule_set_version: event.target.value }))} /></label>
                  </div>
                  <label className="block text-sm text-ink-muted">Review reason<textarea rows={2} className={INPUT} value={decision.reason} required maxLength={2000} onChange={event => setDecision(current => ({ ...current, reason: event.target.value }))} /></label>
                  {!!selected.draft.extraction_warnings.length && <label className="flex items-start gap-2 text-sm text-ink"><input type="checkbox" className="mt-0.5 rounded border-surface-border text-brand focus:ring-brand" required checked={decision.acknowledge_extraction_warnings} onChange={event => setDecision(current => ({ ...current, acknowledge_extraction_warnings: event.target.checked }))} />I reviewed all {selected.draft.extraction_warnings.length} extraction warnings under “Warnings” in Review tools and accept them for publication.</label>}
                  <Button type="submit" loading={busy === 'approval'} disabled={!approvalAllowed || !!busy || !!missingTerms.length}>Approve agreement v{selected.version_number}</Button>
                </fieldset>
              </form>
            )}

            <div className="grid gap-4 lg:grid-cols-2">
              <div className="rounded-xl border border-surface-border bg-surface p-5">
                <h3 className="flex items-center gap-2 text-sm font-semibold text-ink"><History size={16} />Version history</h3>
                <div className="mt-3 flex flex-wrap gap-2">{versions.map(version => <button key={version.version_number} type="button" disabled={!!busy || detailLoading} onClick={() => { setSelected(version); setDecision(blankDecision()); setError(''); setNotice(''); setLookup(null); setLookupMessage(''); setAsOf(version.draft.effective_from) }} className={`rounded-lg border px-3 py-2 text-sm ${selected.version_number === version.version_number ? 'border-brand bg-brand/5' : 'border-surface-border hover:bg-surface-muted'}`}><VersionBadge version={version} /></button>)}</div>
                <div className="mt-3 flex justify-between text-xs text-ink-muted"><button type="button" disabled={historyOffset === 0 || detailLoading || !!busy} className="disabled:opacity-40" onClick={() => historyPage(Math.max(0, historyOffset - PAGE_SIZE))}>Newer versions</button><button type="button" disabled={versions.length < PAGE_SIZE || detailLoading || !!busy} className="disabled:opacity-40" onClick={() => historyPage(historyOffset + PAGE_SIZE)}>Older versions</button></div>
              </div>
              <form onSubmit={lookupApproved} className="rounded-xl border border-surface-border bg-surface p-5">
                <h3 className="text-sm font-semibold text-ink">Approved reference on a date</h3>
                <div className="mt-3 flex flex-wrap items-end gap-2"><label className="min-w-0 flex-1 text-xs text-ink-muted">Reference date<input type="date" className={INPUT} value={asOf} required onChange={event => setAsOf(event.target.value)} /></label><Button type="submit" variant="secondary" className="py-2" loading={busy === 'lookup'} disabled={!!busy}>Find</Button></div>
                {lookupMessage && <p role="status" className="mt-3 text-sm text-ink-muted">{lookupMessage}</p>}
                {lookup && <div role="status" className="mt-3 space-y-2 text-sm text-ink"><p>Approved v{lookup.version_number} · {lookup.draft.effective_from} → {lookup.draft.effective_to}</p><button type="button" className="text-brand underline" onClick={() => { setSelected(lookup); setDecision(blankDecision()); setNotice(''); setError('') }}>View effective version</button></div>}
              </form>
            </div>
          </>
        ) : !detailLoading && (
          <div className="paper-empty rounded-xl border border-dashed border-surface-border bg-surface p-8 text-center"><FilePlus2 className="mx-auto h-9 w-9 text-ink-faint" /><h2 className="mt-4 font-semibold text-ink">Review your agreement master</h2><p className="mx-auto mt-2 max-w-md text-sm leading-6 text-ink-muted">Start from an extracted document or create a draft. Review the terms, approve a version, then use it to reconcile an invoice.</p><Button type="button" className="mt-5" onClick={() => beginNew()}>Create agreement draft</Button></div>
        )}

      </section>
    </div>
    </div>
  )
}
