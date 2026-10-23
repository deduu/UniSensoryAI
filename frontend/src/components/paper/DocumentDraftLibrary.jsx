import { useEffect, useRef, useState } from 'react'
import { formatError } from '../../paper/helpers.js'
import { documentDraftLabel, documentRoleLabel } from '../../paper/draftSelection.js'
import './casePreparation.css'

const PAGE_SIZE = 12

/** Render exact saved versions; preparation never silently selects a later revision. */
export function DocumentDraftCards({ items = [], onOpen, onPrepare }) {
  return <div className="paper-draft-grid">{items.map(record => <article className="paper-draft-card" key={`${record.draft_id}:${record.version_number}`}>
    <header><div><p className="paper-draft-caption">{documentRoleLabel(record.role)} · v{record.version_number}</p><h3>{documentDraftLabel(record)}</h3></div><span className={`paper-preparation-badge ${record.status === 'reviewed' ? 'is-satisfied' : ''}`}>{record.status === 'reviewed' ? 'Reviewed' : 'Draft'}</span></header>
    {record.document?.fields?.vendor_name && <p>{record.document.fields.vendor_name}</p>}
    <p className="paper-draft-caption">{record.status === 'reviewed' ? 'Reviewed source fields. Case readiness is checked separately.' : 'Review fields against the original, then save a reviewed version.'}</p>
    <footer><button type="button" className="paper-secondary" disabled={!onOpen} onClick={() => onOpen?.(record)}>Review draft</button>{record.role === 'rent_invoice' && record.status === 'reviewed' && onPrepare && <button type="button" className="paper-primary" onClick={() => onPrepare(record)}>Prepare case</button>}</footer>
  </article>)}</div>
}

/** Search and page saved drafts without changing selected source records. */
export default function DocumentDraftLibrary({ api, onOpen, onPrepare, refreshKey, active = true }) {
  const [query, setQuery] = useState('')
  const [role, setRole] = useState('')
  const [status, setStatus] = useState('')
  const [offset, setOffset] = useState(0)
  const [page, setPage] = useState({ items: [], total: 0 })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)
  const request = useRef(0)
  useEffect(() => {
    const current = ++request.current
    if (!active) return undefined
    let mounted = true
    setLoading(true); setError('')
    const timer = setTimeout(() => {
      Promise.resolve().then(() => api.listDocumentDrafts({ q: query.trim() || undefined, role: role || undefined, status: status || undefined, limit: PAGE_SIZE, offset }))
        .then(result => { if (mounted && current === request.current) setPage(result) })
        .catch(err => { if (mounted && current === request.current) setError(formatError(err)) })
        .finally(() => { if (mounted && current === request.current) setLoading(false) })
    }, query ? 250 : 0)
    return () => { mounted = false; clearTimeout(timer) }
  }, [api, active, query, role, status, offset, refreshKey, retry])
  const change = setter => event => { setter(event.target.value); setOffset(0) }
  return <section className="paper-panel paper-preparation" aria-label="Saved document drafts">
    <div className="paper-preparation-heading"><div><h2>Saved document drafts</h2><p>Review each source independently. Prepare a case from a reviewed invoice when you are ready.</p></div><button type="button" className="paper-secondary" disabled={loading} onClick={() => setRetry(value => value + 1)}>Refresh drafts</button></div>
    <div className="paper-preparation-filters"><label className="paper-preparation-search">Find a saved draft<input className="paper-input" value={query} placeholder="Invoice number or document reference" onChange={change(setQuery)} /></label><label>Document role<select className="paper-input" value={role} onChange={change(setRole)}><option value="">All document roles</option>{['rent_invoice', 'tax_invoice', 'utility_statement', 'supporting_document'].map(value => <option key={value} value={value}>{documentRoleLabel(value)}</option>)}</select></label><label>Review status<select className="paper-input" value={status} onChange={change(setStatus)}><option value="">All statuses</option><option value="draft">Draft</option><option value="reviewed">Reviewed</option></select></label></div>
    <div aria-live="polite">{loading && <p className="paper-draft-caption">Loading saved drafts…</p>}{error && <div className="paper-preparation-error" role="alert"><p>{error}</p><button type="button" className="paper-secondary" onClick={() => setRetry(value => value + 1)}>Retry drafts</button></div>}</div>
    {!error && !loading && <>{page.items?.length ? <DocumentDraftCards items={page.items} onOpen={onOpen} onPrepare={onPrepare} /> : <p className="paper-preparation-empty">No saved drafts found. Review an extraction and save its document draft first.</p>}<nav className="paper-preparation-pagination" aria-label="Saved draft pages"><button type="button" className="paper-secondary" disabled={!offset} onClick={() => setOffset(value => Math.max(0, value - PAGE_SIZE))}>Previous drafts</button><span>{page.total ? `${offset + 1}–${Math.min(offset + PAGE_SIZE, page.total)} of ${page.total}` : '0 drafts'}</span><button type="button" className="paper-secondary" disabled={offset + PAGE_SIZE >= page.total} onClick={() => setOffset(value => value + PAGE_SIZE)}>Next drafts</button></nav></>}
  </section>
}
