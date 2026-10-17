import { FileText, Trash2 } from 'lucide-react'
import JobStatusBadge from './JobStatusBadge'
import { modelDescription, modelLabel } from '../../jobs/presentation'

function timeAgo(dateStr) {
  if (!dateStr) return ''
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}

export default function JobRow({ job, onClick, onDelete }) {
  return (
    <tr
      onClick={() => onClick?.(job)}
      className="cursor-pointer border-b border-surface-border transition-colors hover:bg-surface-subtle"
    >
      <td className="px-4 py-3">
        <div className="flex items-center gap-3">
          <FileText className="h-4 w-4 shrink-0 text-ink-faint" />
          <span className="min-w-0"><span className="block truncate text-sm font-medium text-ink">{job.filename || job.job_id}</span>{job.meta?.workflow === 'paper_extraction' && <span className="block text-xs text-ink-muted">PAPER extraction</span>}</span>
        </div>
      </td>
      <td className="px-4 py-3">
        <JobStatusBadge status={job.status} />
      </td>
      <td title={modelDescription(job)} className="px-4 py-3 text-sm text-ink-muted">{modelLabel(job)}</td>
      <td className="px-4 py-3 text-sm text-ink-muted">{job.documents?.length || 0}</td>
      <td className="px-4 py-3 text-sm text-ink-muted">{timeAgo(job.created_at)}</td>
      <td className="px-4 py-3">
        {onDelete && (
          <button
            onClick={(e) => {
              e.stopPropagation()
              onDelete(job)
            }}
            className="rounded p-1 text-ink-faint transition-colors hover:bg-red-50 hover:text-red-500"
            title="Delete job"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        )}
      </td>
    </tr>
  )
}
