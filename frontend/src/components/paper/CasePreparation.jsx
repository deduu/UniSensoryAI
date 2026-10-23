import { useEffect, useRef, useState } from 'react'
import { formatError } from '../../paper/helpers.js'
import { addReviewedDraft, documentDraftLabel, documentRoleLabel, draftReference, hydrateDraftSelection, packageFromDraftSelection, removeSelectedDraft } from '../../paper/draftSelection.js'
import './casePreparation.css'

const PAGE_SIZE = 8
const ROLE_KEYS = { tax_invoice: 'tax_invoices', utility_statement: 'utility_statements', supporting_document: 'supporting_documents' }
const recordKey = record => `${record?.draft_id}:${record?.version_number}`
const checkStatus = check => {
  if (check.status === 'not_applicable') return 'Not applicable'
  if (['satisfied', 'passed', 'present', 'ready'].includes(check.status)) return 'Ready'
  if (check.requirement === 'optional' && !check.blocking) return check.status === 'missing' ? 'Not provided · optional' : 'Optional'
  if (check.blocking) return 'Action needed'
  return ({ missing: 'Missing value', failed: 'Needs attention', unresolved: 'Needs review', review: 'Needs review' })[check.status] || 'Needs review'
}
const checkTone = check => check.status === 'not_applicable' || (check.requirement === 'optional' && !check.blocking) ? 'is-neutral' : ['satisfied', 'passed', 'present', 'ready'].includes(check.status) ? 'is-satisfied' : check.blocking ? 'is-blocking' : 'is-attention'

function ReadinessCheck({ check, onOpenSource }) {
  return <li className={`paper-readiness-check ${checkTone(check)}`}><div><strong>{check.label || check.key}</strong><span className="paper-preparation-badge">{({ required: 'Required', conditional: 'Conditional', optional: 'Optional' })[check.requirement] || 'Workflow check'}</span><span className="paper-readiness-state">{checkStatus(check)}</span></div>{check.reason && <p>{check.reason}</p>}{check.source_document_ids?.length > 0 && onOpenSource && <div className="paper-preparation-source-links">{check.source_document_ids.map((id, index) => <button className="paper-source-link" type="button" key={`${id}:${index}`} onClick={() => onOpenSource(id)}>View source{check.source_document_ids.length > 1 ? ` ${index + 1}` : ''}</button>)}</div>}</li>
}

/** Display server-owned readiness rules without creating financial or approval conclusions. */
export function ReadinessChecklist({ readiness, onOpenSource }) {
  if (!readiness) return <div className="paper-preparation-empty">Check readiness after selecting your reviewed documents and confirming their contract. Changes require a fresh check.</div>
  const checks = readiness.checks || []
  const priority = checks.filter(check => check.blocking || (!['satisfied', 'passed', 'present', 'ready', 'not_applicable'].includes(check.status) && check.requirement !== 'optional'))
  const secondary = checks.filter(check => !priority.includes(check))
  return <section className="paper-readiness" aria-label="Case readiness checklist"><header><div><h3>{readiness.ready ? 'Ready to run reconciliation' : 'Complete the checks below'}</h3><p>Readiness checks document completeness and selection. Reconciliation will report matching results separately.</p></div><span className={`paper-preparation-badge ${readiness.ready ? 'is-satisfied' : 'is-attention'}`}>{readiness.ready ? 'Ready' : 'Action needed'}</span></header>
    {readiness.policy_id && <p className="paper-draft-caption">Requirements: {readiness.policy_id}{readiness.policy_version != null ? ` · version ${readiness.policy_version}` : ''}</p>}
    {priority.length > 0 && <ul className="paper-readiness-list">{priority.slice(0, 8).map((check, index) => <ReadinessCheck key={`${check.key}:${index}`} check={check} onOpenSource={onOpenSource} />)}</ul>}
    {priority.length > 8 && <details className="paper-readiness-other"><summary>{priority.length - 8} more checks need attention</summary><ul className="paper-readiness-list">{priority.slice(8).map((check, index) => <ReadinessCheck key={`${check.key}:${index}`} check={check} onOpenSource={onOpenSource} />)}</ul></details>}
    {secondary.length > 0 && <details className="paper-readiness-other" open={!priority.length || undefined}><summary>{secondary.length} completed, optional or not-applicable {secondary.length === 1 ? 'check' : 'checks'}</summary><ul className="paper-readiness-list">{secondary.map((check, index) => <ReadinessCheck key={`${check.key}:${index}`} check={check} onOpenSource={onOpenSource} />)}</ul></details>}
    {!checks.length && <p className="paper-draft-caption">No field checks were returned. The server decides whether reconciliation is available.</p>}
  </section>
}

/** Choose exact reviewed supporting versions and explicitly request readiness before matching. */
export default function CasePreparation({ api, package: pkg, selection, onSelectionChange, onPackageChange, readiness, onCheck, onRun, disabled = false, onOpenSource }) {
  const [role, setRole] = useState('tax_invoice')
  const [query, setQuery] = useState('')
  const [offset, setOffset] = useState(0)
  const [page, setPage] = useState({ items: [], total: 0 })
  const [records, setRecords] = useState([])
  const [loading, setLoading] = useState(false)
  const [hydrating, setHydrating] = useState(Boolean(selection?.invoice))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [selectionError, setSelectionError] = useState('')
  const [retry, setRetry] = useState(0)
  const request = useRef(0)
  const selectionKey = JSON.stringify(selection || null)
  const currentSelection = useRef(selectionKey)
  currentSelection.current = selectionKey
  const currentPackage = useRef(pkg)
  currentPackage.current = pkg
  const mounted = useRef(false)
  useEffect(() => { mounted.current = true; return () => { mounted.current = false } }, [])
  useEffect(() => {
    let active = true
    setRecords([]); setSelectionError('')
    const selected = JSON.parse(selectionKey)
    if (!selected?.invoice) { setHydrating(false); return undefined }
    setHydrating(true)
    hydrateDraftSelection(api, selected).then(result => { if (active) setRecords(result) }).catch(err => { if (active) setSelectionError(formatError(err)) }).finally(() => { if (active) setHydrating(false) })
    return () => { active = false }
  }, [api, selectionKey, retry])
  useEffect(() => {
    const current = ++request.current
    let active = true
    setLoading(true); setError('')
    const timer = setTimeout(() => {
      Promise.resolve().then(() => api.listDocumentDrafts({ role, status: 'reviewed', q: query.trim() || undefined, limit: PAGE_SIZE, offset }))
        .then(result => { if (active && current === request.current) setPage(result) })
        .catch(err => { if (active && current === request.current) setError(formatError(err)) })
        .finally(() => { if (active && current === request.current) setLoading(false) })
    }, query ? 250 : 0)
    return () => { active = false; clearTimeout(timer) }
  }, [api, role, query, offset, retry])
  const locked = disabled || busy || hydrating || Boolean(selectionError) || !selection?.invoice || !onSelectionChange || !onPackageChange
  const apply = (next, values) => {
    // Contract/allocation edits may happen while an exact document lookup is pending.
    const nextPackage = packageFromDraftSelection(currentPackage.current, next, values)
    onSelectionChange(next)
    onPackageChange(nextPackage)
  }
  const add = async record => {
    const intent = currentSelection.current
    setBusy(true); setError('')
    try {
      const exact = await api.documentDraftVersion(record.draft_id, record.version_number)
      if (!mounted.current || currentSelection.current !== intent) return
      if (recordKey(exact) !== recordKey(record) || exact.role !== role) throw new Error('The document service did not return the requested role and version.')
      const next = addReviewedDraft(selection, exact, records)
      apply(next, [...records, exact])
    } catch (err) { if (mounted.current && currentSelection.current === intent) setError(formatError(err)) }
    finally { if (mounted.current) setBusy(false) }
  }
  const remove = record => {
    try { apply(removeSelectedDraft(selection, record.role, draftReference(record)), records.filter(item => recordKey(item) !== recordKey(record))) }
    catch (err) { setError(formatError(err)) }
  }
  const supports = records.filter(record => record.role !== 'rent_invoice')
  return <section className="paper-panel paper-preparation" aria-label="Prepare invoice case"><div className="paper-preparation-heading"><div><h2>Prepare this case</h2><p>Select the reviewed documents for this invoice. Confirm its contract, check readiness, then run reconciliation.</p></div></div>
    <div className="paper-preparation-invoice"><div><span className="paper-draft-caption">Primary invoice{selection?.invoice?.version_number ? ` · reviewed v${selection.invoice.version_number}` : ''}</span><h3>{pkg?.invoice?.fields?.invoice_number || 'Select a reviewed invoice'}</h3><p className="paper-draft-caption">To use another invoice, choose Prepare case from Saved document drafts.</p></div>{pkg?.invoice?.source_document_id && onOpenSource && <button className="paper-secondary" type="button" onClick={() => onOpenSource(pkg.invoice.source_document_id)}>View invoice source</button>}</div>
    {hydrating && <p className="paper-draft-caption" role="status">Loading exact selected document versions…</p>}
    {selectionError && <div className="paper-preparation-error" role="alert"><p>{selectionError}</p><button type="button" className="paper-secondary" onClick={() => setRetry(value => value + 1)}>Retry selected documents</button></div>}
    <div className="paper-preparation-selected"><h3>Selected supporting documents ({supports.length})</h3>{supports.length ? <ul>{supports.map(record => <li key={recordKey(record)}><div><strong>{documentDraftLabel(record)}</strong><span>{documentRoleLabel(record.role)} · reviewed v{record.version_number}</span></div><div>{onOpenSource && <button type="button" className="paper-source-link" onClick={() => onOpenSource(record.document.source_document_id)}>View source</button>}<button type="button" className="paper-secondary" disabled={locked} onClick={() => remove(record)}>Remove<span className="sr-only"> {documentDraftLabel(record)}</span></button></div></li>)}</ul> : <p className="paper-draft-caption">No supporting documents selected. The requirements checklist will show which are needed.</p>}</div>
    <details className="paper-preparation-picker"><summary>Add reviewed supporting documents</summary><div className="paper-preparation-filters"><label>Document role<select className="paper-input" value={role} disabled={busy} onChange={event => { setRole(event.target.value); setOffset(0) }}>{Object.keys(ROLE_KEYS).map(value => <option key={value} value={value}>{documentRoleLabel(value)}</option>)}</select></label><label className="paper-preparation-search">Find reviewed documents<input className="paper-input" value={query} placeholder="Document number or reference" onChange={event => { setQuery(event.target.value); setOffset(0) }} /></label></div>
      {loading && <p className="paper-draft-caption" role="status">Loading reviewed documents…</p>}{error && <div className="paper-preparation-error" role="alert"><p>{error}</p><button type="button" className="paper-secondary" onClick={() => setRetry(value => value + 1)}>Retry documents</button></div>}
      {!loading && !error && <>{page.items?.length ? <ul className="paper-preparation-choices">{page.items.map(record => {
        const alreadySelected = records.some(item => recordKey(item) === recordKey(record) || (item.document?.source_document_id && item.document.source_document_id === record.document?.source_document_id))
        return <li key={recordKey(record)}><div><strong>{documentDraftLabel(record)}</strong><span>{documentRoleLabel(record.role)} · reviewed v{record.version_number}</span></div><button type="button" className="paper-secondary" disabled={locked || alreadySelected || record.status !== 'reviewed'} onClick={() => add(record)}>{alreadySelected ? 'Already selected' : 'Add to case'}</button></li>
      })}</ul> : <p className="paper-draft-caption">No reviewed documents found for this role. Save a reviewed document draft first.</p>}<nav className="paper-preparation-pagination" aria-label="Supporting document pages"><button type="button" className="paper-secondary" disabled={loading || !offset} onClick={() => setOffset(value => Math.max(0, value - PAGE_SIZE))}>Previous documents</button><span>{page.total ? `${offset + 1}–${Math.min(offset + PAGE_SIZE, page.total)} of ${page.total}` : '0 documents'}</span><button type="button" className="paper-secondary" disabled={loading || offset + PAGE_SIZE >= page.total} onClick={() => setOffset(value => value + PAGE_SIZE)}>Next documents</button></nav></>}
    </details>
    <ReadinessChecklist readiness={readiness} onOpenSource={onOpenSource} />
    <div className="paper-preparation-actions"><button type="button" className="paper-secondary" disabled={disabled || busy || hydrating || Boolean(selectionError) || !selection?.invoice || !onCheck} onClick={() => onCheck?.()}>Check readiness</button><button type="button" className="paper-primary" disabled={disabled || busy || hydrating || Boolean(selectionError) || !selection?.invoice || readiness?.ready !== true || !onRun} onClick={() => onRun?.()}>Run reconciliation</button></div>
  </section>
}
