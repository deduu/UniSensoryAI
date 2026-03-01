import { useState } from 'react'
import { X, FileText, RotateCcw, Trash2 } from 'lucide-react'
import JobStatusBadge from './JobStatusBadge'
import Button from '../ui/Button'
import { useJobPolling } from '../../hooks/useJobPolling'
import { useApp } from '../../context/AppContext'
import { useJobs } from '../../context/JobContext'
import { deleteJob, retryJob } from '../../api/jobs'

export default function JobDetailPanel({ job, onClose }) {
  const { backendUrl } = useApp()
  const { updateJob, removeJob } = useJobs()
  const [deleting, setDeleting] = useState(false)
  const [retrying, setRetrying] = useState(false)
  const [actionError, setActionError] = useState(null)

  // Poll while viewing a non-terminal job (status is always lowercase from API layer)
  const isTerminal = ['completed', 'failed'].includes(job?.status)
  useJobPolling(isTerminal ? null : job?.job_id)

  if (!job) return null

  const isFailed = job.status === 'failed'

  async function handleRetry() {
    setRetrying(true)
    setActionError(null)
    try {
      await retryJob(job.job_id, backendUrl)
      updateJob(job.job_id, { status: 'pending', documents: [] })
    } catch (err) {
      setActionError(err.message || 'Retry failed')
    } finally {
      setRetrying(false)
    }
  }

  async function handleDelete() {
    setDeleting(true)
    setActionError(null)
    try {
      await deleteJob(job.job_id, backendUrl)
      removeJob(job.job_id)
      onClose()
    } catch (err) {
      setActionError(err.message || 'Delete failed')
      setDeleting(false)
    }
  }

  return (
    <div className="fixed inset-y-0 right-0 z-40 w-full max-w-md animate-slide-in border-l border-surface-border bg-white shadow-modal">
      <div className="flex h-16 items-center justify-between border-b border-surface-border px-6">
        <h2 className="text-lg font-semibold text-ink">Job Details</h2>
        <button
          onClick={onClose}
          className="rounded-lg p-1 text-ink-muted transition-colors hover:bg-surface-subtle"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      <div className="overflow-y-auto p-6" style={{ maxHeight: 'calc(100vh - 4rem)' }}>
        <div className="space-y-4">
          <div>
            <label className="text-xs font-semibold uppercase text-ink-muted">Job ID</label>
            <p className="mt-1 font-mono text-sm text-ink">{job.job_id}</p>
          </div>

          <div>
            <label className="text-xs font-semibold uppercase text-ink-muted">Status</label>
            <div className="mt-1">
              <JobStatusBadge status={job.status} />
            </div>
          </div>

          <div>
            <label className="text-xs font-semibold uppercase text-ink-muted">File</label>
            <p className="mt-1 text-sm text-ink">{job.filename || '—'}</p>
          </div>

          <div>
            <label className="text-xs font-semibold uppercase text-ink-muted">Model</label>
            <p className="mt-1 text-sm text-ink">{job.model_id || '—'}</p>
          </div>

          <div>
            <label className="text-xs font-semibold uppercase text-ink-muted">Created</label>
            <p className="mt-1 text-sm text-ink">
              {job.created_at ? new Date(job.created_at).toLocaleString() : '—'}
            </p>
          </div>

          {/* Error details for failed jobs */}
          {isFailed && job.meta?.error && (
            <div>
              <label className="text-xs font-semibold uppercase text-red-500">Error</label>
              <p className="mt-1 rounded bg-red-50 p-2 text-sm text-red-700">{job.meta.error}</p>
            </div>
          )}

          {/* Action error */}
          {actionError && (
            <p className="rounded bg-red-50 px-3 py-2 text-sm text-red-700">{actionError}</p>
          )}

          {/* Action buttons */}
          <div className="flex gap-3 border-t border-surface-border pt-4">
            {isFailed && (
              <Button onClick={handleRetry} loading={retrying} variant="secondary">
                <RotateCcw className="mr-1.5 h-4 w-4" />
                Retry
              </Button>
            )}
            <Button onClick={handleDelete} loading={deleting} variant="danger">
              <Trash2 className="mr-1.5 h-4 w-4" />
              Delete
            </Button>
          </div>

          {/* Documents */}
          {job.documents?.length > 0 && (
            <div>
              <label className="text-xs font-semibold uppercase text-ink-muted">
                Documents ({job.documents.length})
              </label>
              <div className="mt-2 space-y-2">
                {job.documents.map((doc, i) => (
                  <div
                    key={doc.id || i}
                    className="rounded-lg border border-surface-border bg-surface-subtle p-3"
                  >
                    <div className="flex items-center gap-2">
                      <FileText className="h-4 w-4 text-ink-faint" />
                      <span className="text-sm font-medium text-ink">
                        {doc.filename || `Document ${i + 1}`}
                      </span>
                    </div>
                    {doc.content_text && (
                      <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap rounded bg-white p-2 font-mono text-xs text-ink-muted">
                        {doc.content_text}
                      </pre>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
