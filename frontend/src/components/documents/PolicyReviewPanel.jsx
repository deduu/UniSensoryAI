import { useEffect, useMemo, useState } from 'react'
import { AlertCircle, CheckCircle2, Database, FileText, Globe, Loader2, RefreshCw } from 'lucide-react'
import { getPolicyReview, reviewPolicy } from '../../api/policy'
import { useApp } from '../../context/AppContext'

const SOURCE_LABELS = {
  uploaded_document: 'Uploaded document',
  database: 'Database',
  trusted_source: 'Trusted source',
  web_search: 'Web search',
  synthesis: 'Synthesis',
}

const SEVERITY_STYLES = {
  high: 'border-red-400/25 bg-red-400/10 text-red-300',
  medium: 'border-amber-400/25 bg-amber-400/10 text-amber-200',
  low: 'border-emerald-400/25 bg-emerald-400/10 text-emerald-300',
}

function getClauseRoleLabel(finding, clause, index) {
  if (finding.source === 'uploaded_document') {
    return index === 0 ? 'Proposed clause A' : 'Proposed clause B'
  }
  if (finding.source === 'database') {
    return index === 0 ? 'Proposed clause' : 'Stored policy clause'
  }
  if (finding.source === 'web_search') {
    return index === 0 ? 'Proposed clause' : 'External policy clause'
  }
  if (finding.source === 'trusted_source') {
    return index === 0 ? 'Proposed clause' : 'Trusted policy clause'
  }
  return SOURCE_LABELS[clause.source] || clause.source
}

function Toggle({ checked, onChange, label, icon: Icon }) {
  return (
    <label className="flex items-center gap-2 rounded-lg border border-surface-border bg-surface-muted/40 px-3 py-2 text-xs text-ink-muted">
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="h-3.5 w-3.5 rounded border-surface-border bg-surface text-brand focus:ring-brand/30 focus:ring-offset-0"
      />
      <Icon className="h-3.5 w-3.5 text-ink-faint" />
      <span>{label}</span>
    </label>
  )
}

function FindingCard({ finding }) {
  const severityClass = SEVERITY_STYLES[finding.severity] || SEVERITY_STYLES.medium
  const sourceLabel = SOURCE_LABELS[finding.source] || finding.source
  const sharedTokens = finding.metadata?.shared_tokens || []
  const conflictReason = finding.metadata?.conflict_reason

  return (
    <article className="rounded-xl border border-surface-border bg-surface-muted/20 p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h4 className="text-sm font-semibold text-ink">{finding.title}</h4>
          <p className="mt-1 text-xs leading-5 text-ink-muted">{finding.description}</p>
        </div>
        <div className="flex items-center gap-2">
          <span className={`rounded-md border px-2 py-1 text-[11px] font-medium capitalize ${severityClass}`}>
            {finding.severity}
          </span>
          <span className="rounded-md border border-surface-border bg-surface px-2 py-1 text-[11px] text-ink-faint">
            {sourceLabel}
          </span>
        </div>
      </div>

      {conflictReason && (
        <div className="mt-3 rounded-lg border border-brand/15 bg-brand/5 p-3">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-brand/80">
            Why this conflicts
          </p>
          <p className="mt-1 text-xs leading-5 text-ink-muted">{conflictReason}</p>
        </div>
      )}

      {finding.clauses?.length > 0 && (
        <div className="mt-3 space-y-2">
          {finding.clauses.slice(0, 2).map((clause, index) => (
            <div key={`${finding.title}-${index}`} className="rounded-lg border border-surface-border bg-surface/70 p-3">
              <div className="flex flex-wrap items-center gap-2 text-[11px] text-ink-faint">
                <span className="font-medium text-ink">{getClauseRoleLabel(finding, clause, index)}</span>
                {clause.filename && <span>{clause.filename}</span>}
                {clause.location && (
                  <a
                    href={clause.location}
                    target="_blank"
                    rel="noreferrer"
                    className="text-brand hover:text-brand/80"
                  >
                    Open source
                  </a>
                )}
              </div>
              <p className="mt-2 whitespace-pre-wrap break-words text-xs leading-5 text-ink-muted">
                {clause.text}
              </p>
            </div>
          ))}
        </div>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-[11px] text-ink-faint">
        <span>Confidence {Math.round((finding.confidence || 0) * 100)}%</span>
        {finding.metadata?.reference_excerpt_source === 'page_text' && (
          <span>Matched from external page text</span>
        )}
        {finding.metadata?.url && (
          <a
            href={finding.metadata.url}
            target="_blank"
            rel="noreferrer"
            className="text-brand hover:text-brand/80"
          >
            View cited result
          </a>
        )}
      </div>

      {sharedTokens.length > 0 && (
        <div className="mt-3">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-faint">
            Shared concepts
          </p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {sharedTokens.slice(0, 6).map((token) => (
              <span
                key={token}
                className="rounded-md border border-surface-border bg-surface px-2 py-1 text-[11px] text-ink-muted"
              >
                {token}
              </span>
            ))}
          </div>
        </div>
      )}

      {finding.recommendation && (
        <div className="mt-3 rounded-lg border border-brand/15 bg-brand/5 p-3">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-brand/80">
            Recommendation
          </p>
          <p className="mt-1 text-xs leading-5 text-ink-muted">{finding.recommendation}</p>
        </div>
      )}
    </article>
  )
}

export default function PolicyReviewPanel({ doc, onResultChange }) {
  const { backendUrl } = useApp()
  const [includeDatabase, setIncludeDatabase] = useState(true)
  const [includeTrustedSources, setIncludeTrustedSources] = useState(true)
  const [includeWebSearch, setIncludeWebSearch] = useState(true)
  const [focus, setFocus] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    setResult(doc?.policy_review || null)
    setError(null)
    setLoading(false)
  }, [doc?.id, doc?.job_id, doc?.policy_review])

  useEffect(() => {
    if (!doc?.job_id || doc?.policy_review) return

    let cancelled = false
    getPolicyReview(doc.job_id, backendUrl)
      .then((savedReview) => {
        if (cancelled) return
        setResult(savedReview)
        onResultChange?.(savedReview)
      })
      .catch((reviewError) => {
        if (reviewError.status !== 404) setError(reviewError.message || 'Could not load saved policy review')
      })

    return () => {
      cancelled = true
    }
  }, [backendUrl, doc?.job_id, doc?.policy_review, onResultChange])

  const counts = useMemo(() => {
    const findings = result?.findings || []
    return findings.reduce(
      (acc, finding) => {
        acc.total += 1
        acc[finding.severity] += 1
        return acc
      },
      { total: 0, high: 0, medium: 0, low: 0 }
    )
  }, [result])

  const notes = useMemo(
    () => (result?.agent_results || []).flatMap((agent) => (agent.notes || []).map((note) => ({ agent: agent.agent_name, note }))),
    [result]
  )
  const degradedAgents = useMemo(
    () =>
      (result?.agent_results || []).filter(
        (agent) => agent.metadata?.error || agent.metadata?.timed_out || agent.metadata?.degraded
      ),
    [result]
  )

  const canRun = Boolean(doc?.job_id) && doc?.job_status === 'completed'

  const handleRun = async () => {
    if (!canRun || loading) return
    setLoading(true)
    setError(null)
    try {
      const review = await reviewPolicy(
        doc.job_id,
        {
          include_database: includeDatabase,
          include_trusted_sources: includeTrustedSources,
          include_web_search: includeWebSearch,
          focus: focus.trim() || null,
        },
        backendUrl
      )
      setResult(review)
      onResultChange?.(review)
    } catch (reviewError) {
      setError(reviewError.message || 'Policy review failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-surface-border px-4 py-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-ink">Policy review</p>
            <p className="mt-1 text-xs leading-5 text-ink-faint">
              Run the backend orchestrator against this completed document and collect contradictions from the uploaded text,
              stored references, trusted policy URLs, and public web search.
            </p>
          </div>
          <button
            type="button"
            onClick={handleRun}
            disabled={!canRun || loading}
            className="inline-flex items-center gap-2 rounded-lg bg-brand px-3 py-2 text-xs font-medium text-white transition-colors hover:bg-brand/90 disabled:cursor-not-allowed disabled:bg-brand/40"
          >
            {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
            {result ? 'Run again' : 'Run review'}
          </button>
        </div>

        <div className="mt-3 grid gap-2 md:grid-cols-3">
          <Toggle
            checked={includeDatabase}
            onChange={setIncludeDatabase}
            label="Compare with stored documents"
            icon={Database}
          />
          <Toggle
            checked={includeTrustedSources}
            onChange={setIncludeTrustedSources}
            label="Compare with trusted policy URLs"
            icon={FileText}
          />
          <Toggle
            checked={includeWebSearch}
            onChange={setIncludeWebSearch}
            label="Search public web references"
            icon={Globe}
          />
        </div>

        <div className="mt-3">
          <input
            type="text"
            value={focus}
            onChange={(event) => setFocus(event.target.value)}
            placeholder="Optional focus, for example: student records, confidential data, records retention"
            className="w-full rounded-lg border border-surface-border bg-surface-muted px-3 py-2 text-sm text-ink placeholder:text-ink-faint focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/20"
          />
        </div>

        {!canRun && (
          <div className="mt-3 rounded-lg border border-amber-400/25 bg-amber-400/10 px-3 py-2 text-xs text-amber-200">
            Policy review is available after the job reaches completed status.
          </div>
        )}

        {error && (
          <div className="mt-3 flex items-start gap-2 rounded-lg border border-red-400/25 bg-red-400/10 px-3 py-2 text-xs text-red-300">
            <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <span>{error}</span>
          </div>
        )}
      </div>

      <div className="flex-1 overflow-auto px-4 py-4">
        {!result ? (
          <div className="rounded-xl border border-dashed border-surface-border px-4 py-8 text-center">
            <p className="text-sm font-medium text-ink">No review run yet</p>
            <p className="mt-1 text-xs leading-5 text-ink-faint">
              Run the policy review to inspect this document for contradictions and interference risks.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {degradedAgents.length > 0 && (
              <section className="rounded-xl border border-amber-400/25 bg-amber-400/10 p-4">
                <div className="flex items-start gap-3">
                  <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-amber-200" />
                  <div>
                    <p className="text-sm font-semibold text-amber-100">Review completed with limited coverage</p>
                    <p className="mt-1 text-xs leading-5 text-amber-100/80">
                      One or more agents could not complete their full checks, so this result should be treated as partial.
                    </p>
                  </div>
                </div>
              </section>
            )}

            <section className="rounded-xl border border-surface-border bg-surface-muted/20 p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-ink">Review summary</p>
                  <p className="mt-1 text-xs leading-5 text-ink-muted">{result.summary}</p>
                </div>
                <div className="flex flex-wrap items-center gap-2 text-[11px]">
                  <span className="rounded-md border border-surface-border bg-surface px-2 py-1 text-ink-faint">
                    {counts.total} finding{counts.total === 1 ? '' : 's'}
                  </span>
                  <span className="rounded-md border border-red-400/20 bg-red-400/10 px-2 py-1 text-red-300">
                    {counts.high} high
                  </span>
                  <span className="rounded-md border border-amber-400/20 bg-amber-400/10 px-2 py-1 text-amber-200">
                    {counts.medium} medium
                  </span>
                  <span className="rounded-md border border-emerald-400/20 bg-emerald-400/10 px-2 py-1 text-emerald-300">
                    {counts.low} low
                  </span>
                  <span className="rounded-md border border-surface-border bg-surface px-2 py-1 text-ink-faint">
                    {result.metadata?.elapsed_ms ?? 0} ms
                  </span>
                </div>
              </div>
            </section>

            {counts.total === 0 ? (
              <section className="rounded-xl border border-emerald-400/20 bg-emerald-400/10 p-4">
                <div className="flex items-start gap-3">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-300" />
                  <div>
                    <p className="text-sm font-semibold text-emerald-200">No contradictions detected</p>
                    <p className="mt-1 text-xs leading-5 text-emerald-100/80">
                      The configured agents did not find conflicts in this pass. It is still worth opening any cited references
                      or re-running with a more specific focus if you want a tighter review.
                    </p>
                  </div>
                </div>
              </section>
            ) : (
              <section className="space-y-3">
                {result.findings.map((finding, index) => (
                  <FindingCard key={`${finding.title}-${index}`} finding={finding} />
                ))}
              </section>
            )}

            {notes.length > 0 && (
              <section className="rounded-xl border border-surface-border bg-surface-muted/20 p-4">
                <p className="text-sm font-semibold text-ink">Agent notes</p>
                <div className="mt-3 space-y-2">
                  {notes.map(({ agent, note }, index) => (
                    <div key={`${agent}-${index}`} className="rounded-lg border border-surface-border bg-surface/70 px-3 py-2">
                      <p className="text-[11px] font-medium uppercase tracking-wider text-ink-faint">{agent}</p>
                      <p className="mt-1 text-xs leading-5 text-ink-muted">{note}</p>
                    </div>
                  ))}
                </div>
              </section>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
