import JobRow from './JobRow'
import EmptyState from '../ui/EmptyState'
import { FileUp } from 'lucide-react'

export default function JobTable({ jobs, onSelectJob, onDeleteJob, emptyAction }) {
  if (jobs.length === 0) {
    return (
      <EmptyState
        icon={FileUp}
        heading="No jobs yet"
        subtext="Upload a document to start processing"
        actionLabel={emptyAction ? 'Upload Document' : undefined}
        onAction={emptyAction}
      />
    )
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-surface-border bg-white">
      <table className="w-full">
        <thead>
          <tr className="border-b border-surface-border bg-surface-subtle text-left">
            <th className="px-4 py-3 text-xs font-semibold uppercase text-ink-muted">File</th>
            <th className="px-4 py-3 text-xs font-semibold uppercase text-ink-muted">Status</th>
            <th className="px-4 py-3 text-xs font-semibold uppercase text-ink-muted">Model</th>
            <th className="px-4 py-3 text-xs font-semibold uppercase text-ink-muted">Docs</th>
            <th className="px-4 py-3 text-xs font-semibold uppercase text-ink-muted">Created</th>
            <th className="w-12 px-4 py-3"></th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((job) => (
            <JobRow
              key={job.job_id}
              job={job}
              onClick={onSelectJob}
              onDelete={onDeleteJob}
            />
          ))}
        </tbody>
      </table>
    </div>
  )
}
