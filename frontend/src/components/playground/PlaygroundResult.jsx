import { useState } from 'react'
import { Copy, Check, Download, FileText } from 'lucide-react'
import Button from '../ui/Button'
import JobStatusBadge from '../jobs/JobStatusBadge'
import EmptyState from '../ui/EmptyState'

export default function PlaygroundResult({ job }) {
  const [copied, setCopied] = useState(false)

  if (!job) {
    return (
      <EmptyState
        icon={FileText}
        heading="No results yet"
        subtext="Upload a document and click Run to see results"
      />
    )
  }

  const docs = job.documents || []
  const content = docs.map((d) => d.content_text || '').join('\n\n---\n\n')

  const handleCopy = async () => {
    await navigator.clipboard.writeText(content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleDownload = () => {
    const blob = new Blob([content], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `result-${job.job_id}.txt`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-sm font-medium text-ink">Job</span>
          <code className="rounded bg-surface-subtle px-2 py-0.5 font-mono text-xs text-ink-muted">
            {job.job_id}
          </code>
          <JobStatusBadge status={job.status} />
        </div>
        {content && (
          <div className="flex gap-2">
            <Button variant="ghost" onClick={handleCopy}>
              {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
            </Button>
            <Button variant="ghost" onClick={handleDownload}>
              <Download className="h-4 w-4" />
            </Button>
          </div>
        )}
      </div>

      {content ? (
        <pre className="max-h-[65vh] overflow-auto whitespace-pre-wrap rounded-xl border border-surface-border bg-surface-subtle p-4 font-mono text-sm leading-relaxed text-ink">
          {content}
        </pre>
      ) : (
        <div className="flex items-center justify-center rounded-xl border border-surface-border bg-surface-subtle p-12">
          <p className="text-sm text-ink-muted">
            {job.status === 'completed' ? 'No content extracted' : 'Waiting for results...'}
          </p>
        </div>
      )}
    </div>
  )
}
