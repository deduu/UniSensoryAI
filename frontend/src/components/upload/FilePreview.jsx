import { FileText, X } from 'lucide-react'

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export default function FilePreview({ file, index, onRemove }) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-surface-border bg-surface-muted p-3">
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-brand-light">
        <FileText className="h-5 w-5 text-brand" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-ink">{file.name}</p>
        <p className="text-xs text-ink-muted">{formatSize(file.size)}</p>
      </div>
      {onRemove && (
        <button
          onClick={() => onRemove(index)}
          className="rounded p-1 text-ink-faint transition-colors hover:bg-red-50 hover:text-red-500"
        >
          <X className="h-4 w-4" />
        </button>
      )}
    </div>
  )
}
