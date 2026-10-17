import {
  FileText,
  FileSpreadsheet,
  FileImage,
  Presentation,
  File,
} from 'lucide-react'
import Badge from '../ui/Badge'
import { modelDescription, modelLabel } from '../../jobs/presentation'

const FILE_ICONS = {
  pdf: FileText,
  xlsx: FileSpreadsheet,
  xls: FileSpreadsheet,
  csv: FileSpreadsheet,
  png: FileImage,
  jpg: FileImage,
  jpeg: FileImage,
  webp: FileImage,
  gif: FileImage,
  pptx: Presentation,
  ppt: Presentation,
}

function getFileIcon(filename) {
  const ext = filename?.split('.').pop()?.toLowerCase() || ''
  return FILE_ICONS[ext] || File
}

function relativeTime(dateStr) {
  if (!dateStr) return '—'
  const now = Date.now()
  const d = new Date(dateStr).getTime()
  const diff = now - d
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days < 7) return `${days}d ago`
  return new Date(dateStr).toLocaleDateString()
}

export default function DocumentList({
  documents,
  activeDocId,
  selectedIds,
  onSelectDoc,
  onToggleSelect,
}) {
  return (
    <div className="space-y-1">
      {documents.map((doc) => {
        const docId = doc.id ?? doc.job_id
        const isActive = docId === activeDocId
        const isSelected = selectedIds.has(docId)
        const Icon = getFileIcon(doc.filename)
        const preview = doc.content_text
          ? doc.content_text.length > 100
            ? doc.content_text.slice(0, 100) + '…'
            : doc.content_text
          : 'No content extracted'

        return (
          <div
            key={docId}
            onClick={() => onSelectDoc(doc)}
            className={`group flex gap-3 rounded-xl p-3 cursor-pointer transition-all duration-150 ${
              isActive
                ? 'bg-brand/10 border border-brand/20'
                : isSelected
                  ? 'bg-brand/5 border border-transparent'
                  : 'border border-transparent hover:bg-surface-subtle'
            }`}
          >
            {/* Checkbox */}
            <div
              className="flex items-start pt-0.5"
              onClick={(e) => e.stopPropagation()}
            >
              <input
                type="checkbox"
                checked={isSelected}
                onChange={() => onToggleSelect(docId)}
                className="h-3.5 w-3.5 rounded border-surface-border bg-surface-muted text-brand focus:ring-brand/30 focus:ring-offset-0"
              />
            </div>

            {/* Icon */}
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-brand-light">
              <Icon className="h-5 w-5 text-brand" />
            </div>

            {/* Content */}
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <h3 className="truncate text-sm font-semibold text-ink">
                  {doc.filename || 'Untitled'}
                </h3>
                <Badge variant={doc.job_status} dot>
                  {doc.job_status}
                </Badge>
              </div>
              <p className="mt-0.5 truncate font-mono text-xs text-ink-faint leading-relaxed">
                {preview}
              </p>
              <div className="mt-1 flex items-center gap-3 text-xs text-ink-faint">
                <span title={modelDescription(doc)} className="rounded bg-surface-subtle px-1.5 py-0.5 font-mono">
                  {modelLabel(doc)}
                </span>
                <span>{relativeTime(doc.created_at)}</span>
              </div>
            </div>
          </div>
        )
      })}

      {documents.length === 0 && (
        <div className="py-12 text-center text-sm text-ink-muted">
          No documents match your filters
        </div>
      )}
    </div>
  )
}
