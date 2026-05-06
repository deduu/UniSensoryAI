import { Download, X } from 'lucide-react'

export default function BulkActionsBar({ count, onDownload, onDeselect }) {
  if (count === 0) return null

  return (
    <div className="fixed bottom-6 left-1/2 z-40 -translate-x-1/2 animate-slide-up-panel">
      <div className="flex items-center gap-4 rounded-2xl border border-surface-border bg-surface-muted/90 px-5 py-3 shadow-modal backdrop-blur-lg">
        <span className="text-sm font-medium text-ink">
          <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-brand text-xs text-white mr-2">
            {count}
          </span>
          selected
        </span>

        <div className="h-5 w-px bg-surface-border" />

        <button
          onClick={onDownload}
          className="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium text-ink-muted transition-colors hover:bg-surface-subtle hover:text-ink"
        >
          <Download className="h-3.5 w-3.5" />
          Download
        </button>

        <button
          onClick={onDeselect}
          className="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium text-ink-muted transition-colors hover:bg-surface-subtle hover:text-ink"
        >
          <X className="h-3.5 w-3.5" />
          Clear
        </button>
      </div>
    </div>
  )
}
