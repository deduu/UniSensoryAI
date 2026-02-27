import { FileText, Eye } from 'lucide-react'
import Card from '../ui/Card'
import Badge from '../ui/Badge'

export default function DocumentCard({ doc, onViewFull }) {
  const preview = doc.content_text
    ? doc.content_text.length > 150
      ? doc.content_text.slice(0, 150) + '...'
      : doc.content_text
    : 'No content extracted'

  return (
    <Card hover className="flex flex-col">
      <div className="flex items-start gap-3 p-4">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-brand-light">
          <FileText className="h-5 w-5 text-brand" />
        </div>
        <div className="min-w-0 flex-1">
          <h3 className="truncate text-sm font-semibold text-ink">
            {doc.filename || 'Untitled'}
          </h3>
          <div className="mt-1 flex items-center gap-2">
            <Badge variant={doc.job_status}>{doc.job_status}</Badge>
            {doc.model_id && (
              <span className="text-xs text-ink-faint">{doc.model_id}</span>
            )}
          </div>
        </div>
      </div>
      <div className="flex-1 border-t border-surface-border px-4 py-3">
        <p className="font-mono text-xs leading-relaxed text-ink-muted">{preview}</p>
      </div>
      <div className="border-t border-surface-border px-4 py-2">
        <button
          onClick={() => onViewFull(doc)}
          className="flex items-center gap-1.5 text-xs font-medium text-brand transition-colors hover:text-brand-hover"
        >
          <Eye className="h-3.5 w-3.5" />
          View Full
        </button>
      </div>
    </Card>
  )
}
