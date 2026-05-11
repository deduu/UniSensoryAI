import { useState } from 'react'
import { Eye, MessageSquare, Download, Trash2, Loader2, Plus, X as XIcon, Sparkles } from 'lucide-react'
import Badge from '../ui/Badge'

// ─── helpers ────────────────────────────────────────────────────────────────

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i
const IMAGE_EXTS = new Set(['png', 'jpg', 'jpeg', 'webp', 'gif'])

function getExt(filename) {
  return filename?.split('.').pop()?.toLowerCase() || ''
}

function getFriendlyName(doc) {
  const filename = doc.filename || ''
  const bare = filename.replace(/\.[^/.]+$/, '')
  if (!bare || UUID_RE.test(bare)) {
    return IMAGE_EXTS.has(getExt(filename)) ? 'Image extraction' : 'Document'
  }
  return bare
}

function formatSize(bytes) {
  if (!bytes) return '—'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1048576).toFixed(1)} MB`
}

function relativeTime(dateStr) {
  if (!dateStr) return '—'
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days < 7) return `${days}d ago`
  return new Date(dateStr).toLocaleDateString()
}

// ─── Tips Panel (default right-panel content) ─────────────────────────────────

// Single upload entry point lives in the top extraction bar. This panel just
// reinforces the workflow so the right column isn't empty.
function TipsPanel() {
  return (
    <div className="flex flex-col h-full">
      <div className="shrink-0 px-4 py-3.5 border-b border-surface-border">
        <p className="text-sm font-semibold text-ink">Ready when you are</p>
        <p className="text-xs text-ink-muted mt-0.5">Drop files into the top bar to begin</p>
      </div>

      <div className="flex-1 flex flex-col justify-center gap-4 p-4">
        <div className="flex flex-col items-center text-center gap-2">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-brand/10 border border-brand/20">
            <Sparkles className="h-6 w-6 text-brand" />
          </div>
          <p className="text-sm font-medium text-ink">No active work</p>
          <p className="text-xs text-ink-faint max-w-[220px]">
            Add documents above, pick a model, and click{' '}
            <span className="font-semibold text-brand">Extract documents</span>.
          </p>
        </div>

        <div className="rounded-xl border border-surface-border bg-surface-muted/40 p-3 space-y-1">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-ink-faint">Supported</p>
          <p className="text-xs text-ink-muted">PDF, DOCX, XLSX, PPTX, PNG, JPG</p>
          <p className="text-[11px] text-ink-faint">Up to 50 MB per file</p>
        </div>
      </div>
    </div>
  )
}

// ─── Document Preview Panel ───────────────────────────────────────────────────

function DocumentPreviewPanel({
  doc,
  onOpenPreview,
  onChat,
  onDownload,
  onDelete,
  onStartNewExtraction,
}) {
  const [confirmDelete, setConfirmDelete] = useState(false)

  const ext = getExt(doc.filename)
  const typeLabel = ext ? ext.toUpperCase() : '—'
  const displayName = getFriendlyName(doc)
  const internalId = (doc.id || doc.job_id || '').slice(0, 20)

  const handleDeleteClick = () => {
    if (confirmDelete) {
      onDelete(doc)
      setConfirmDelete(false)
    } else {
      setConfirmDelete(true)
      setTimeout(() => setConfirmDelete(false), 3000)
    }
  }

  const META = [
    { label: 'Status',    value: null, badge: true },
    { label: 'Model',     value: doc.model_id || '—' },
    { label: 'Type',      value: typeLabel },
    { label: 'Processed', value: relativeTime(doc.created_at) },
    { label: 'Size',      value: formatSize(doc.file_size) },
  ]

  return (
    <div className="flex flex-col h-full">
      {/* Header — preview label + persistent "New" pill so user can always start fresh */}
      <div className="shrink-0 px-4 py-3.5 border-b border-surface-border">
        <div className="flex items-start justify-between gap-2 mb-1.5">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-ink-faint">
            Document preview
          </p>
          {onStartNewExtraction && (
            <button
              onClick={onStartNewExtraction}
              title="Clear preview and start a new extraction"
              className="inline-flex items-center gap-1 rounded-md border border-brand/25 bg-brand/10 px-2 py-0.5 text-[10px] font-semibold text-brand hover:bg-brand/20 transition-colors"
            >
              <Plus className="h-3 w-3" />
              New
            </button>
          )}
        </div>
        <p className="text-sm font-semibold text-ink truncate">{displayName}</p>
        {internalId && (
          <p className="text-[11px] text-ink-faint font-mono mt-0.5 truncate" title={doc.id || doc.job_id}>
            {internalId}…
          </p>
        )}
      </div>

      {/* Metadata */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 min-h-0">
        <div className="space-y-2.5">
          {META.map(({ label, value, badge }) => (
            <div key={label} className="flex items-center justify-between gap-2 text-xs">
              <span className="text-ink-faint shrink-0">{label}</span>
              {badge ? (
                <Badge variant={doc.job_status} dot>
                  {doc.job_status}
                </Badge>
              ) : (
                <span className="text-ink-muted font-medium text-right truncate">{value}</span>
              )}
            </div>
          ))}
        </div>

        {/* Content snippet */}
        {doc.content_text && (
          <div className="rounded-xl bg-surface-muted/40 border border-surface-border p-3">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-ink-faint mb-1.5">
              Preview
            </p>
            <p className="text-[11px] text-ink-faint leading-relaxed line-clamp-5 font-mono whitespace-pre-wrap break-words">
              {doc.content_text.slice(0, 240)}
              {doc.content_text.length > 240 ? '…' : ''}
            </p>
          </div>
        )}
      </div>

      {/* Actions — primary (filled brand) > secondary (ghost) > destructive */}
      <div className="shrink-0 p-4 pt-3 border-t border-surface-border space-y-1.5">
        {/* Primary — most likely next action */}
        <button
          onClick={() => onOpenPreview(doc)}
          className="w-full flex items-center justify-center gap-2 rounded-xl bg-brand px-3 py-2.5 text-sm font-semibold text-white shadow-glow hover:bg-brand-hover transition-colors"
        >
          <Eye className="h-3.5 w-3.5 shrink-0" />
          Open preview
        </button>

        {/* Secondary — common follow-ups */}
        <div className="grid grid-cols-2 gap-1.5">
          <button
            onClick={() => onChat(doc)}
            className="flex items-center justify-center gap-1.5 rounded-xl bg-white/[0.03] border border-surface-border px-3 py-2 text-xs font-medium text-ink-muted hover:bg-white/[0.06] hover:text-ink transition-colors"
          >
            <MessageSquare className="h-3.5 w-3.5 shrink-0" />
            Chat
          </button>
          <button
            onClick={() => onDownload(doc)}
            className="flex items-center justify-center gap-1.5 rounded-xl bg-white/[0.03] border border-surface-border px-3 py-2 text-xs font-medium text-ink-muted hover:bg-white/[0.06] hover:text-ink transition-colors"
          >
            <Download className="h-3.5 w-3.5 shrink-0" />
            Download
          </button>
        </div>

        {/* Destructive — separated by divider so it can't be hit by accident */}
        <div className="pt-1.5 mt-1.5 border-t border-surface-border/60">
          <button
            onClick={handleDeleteClick}
            className={`w-full flex items-center justify-center gap-1.5 rounded-xl border px-3 py-1.5 text-xs font-medium transition-colors ${
              confirmDelete
                ? 'bg-red-400/10 border-red-400/30 text-red-400 animate-pulse'
                : 'border-transparent text-ink-faint hover:bg-red-400/10 hover:border-red-400/20 hover:text-red-400'
            }`}
          >
            <Trash2 className="h-3 w-3 shrink-0" />
            {confirmDelete ? 'Click again to confirm' : 'Delete'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── Activity Panel (unified upload + processing) ─────────────────────────────

function relativeElapsed(dateStr) {
  if (!dateStr) return null
  const secs = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000)
  if (secs < 60) return `${secs}s`
  const mins = Math.floor(secs / 60)
  if (mins < 60) return `${mins}m`
  const hours = Math.floor(mins / 60)
  return `${hours}h`
}

function ActivityRow({ row, onCancel }) {
  const { kind, label, filename, error } = row
  const isUploading = kind === 'uploading'
  const isError = kind === 'error'
  const isFailed = kind === 'failed'
  const isRed = isError || isFailed

  // Border + icon vary by state but layout stays consistent so the list reads
  // as a single timeline rather than a state-machine takeover.
  const borderClass = isRed
    ? 'border-red-400/30 bg-red-400/5'
    : 'border-surface-border bg-surface-muted/40'

  return (
    <div className={`flex items-center gap-3 rounded-xl border px-3 py-3 ${borderClass}`}>
      {isRed ? (
        <XIcon className="h-4 w-4 shrink-0 text-red-400" />
      ) : (
        <Loader2 className="h-4 w-4 shrink-0 text-amber-400 animate-spin" />
      )}
      <div className="min-w-0 flex-1">
        <p className="text-xs font-medium text-ink truncate" title={filename}>
          {filename}
        </p>
        <p className="text-[11px] text-ink-faint mt-0.5">
          {label}
          {row.elapsed && !isUploading && (
            <span className="ml-1.5 text-ink-faint/70">· {row.elapsed}</span>
          )}
        </p>
        {isRed && error && (
          <p className="text-[11px] text-red-400/80 mt-0.5 truncate" title={error}>
            {error}
          </p>
        )}
      </div>
      {onCancel && row.jobId && !isUploading && (
        <button
          onClick={() => onCancel(row.jobId)}
          aria-label={isFailed ? `Delete ${filename}` : `Cancel ${filename}`}
          title={isFailed ? 'Remove from list' : 'Cancel and remove'}
          className="shrink-0 rounded-md p-1 text-ink-faint hover:bg-red-400/10 hover:text-red-400 transition-colors"
        >
          <XIcon className="h-3.5 w-3.5" />
        </button>
      )}
    </div>
  )
}

function ActivityPanel({
  uploadingFile,
  modelName,
  processingJobs,
  failedJobs = [],
  onCancel,
  uploadError,
}) {
  // Build a unified list. The current in-flight upload (no job_id yet) sits at
  // the top; everything already in the queue follows it; failed jobs trail.
  const rows = []
  if (uploadingFile) {
    rows.push({
      kind: 'uploading',
      filename: uploadingFile.name || 'document',
      label: 'Uploading…',
    })
  }
  if (uploadError) {
    rows.push({
      kind: 'error',
      filename: uploadError.filename || 'document',
      label: 'Upload failed',
      error: uploadError.message,
    })
  }
  for (const job of processingJobs) {
    rows.push({
      kind: 'processing',
      jobId: job.job_id,
      filename: job.filename || job.job_id,
      label: job.status === 'pending' || job.status === 'queued' ? 'Queued' : 'Processing…',
      elapsed: relativeElapsed(job.created_at),
    })
  }
  for (const job of failedJobs) {
    rows.push({
      kind: 'failed',
      jobId: job.job_id,
      filename: job.filename || job.job_id,
      label: 'Extraction failed',
      error: job.error || job.meta?.error || null,
      elapsed: relativeTime(job.updated_at || job.created_at),
    })
  }

  const inFlight = rows.filter((r) => r.kind === 'uploading' || r.kind === 'processing').length
  const failedCount = failedJobs.length

  let summary
  if (inFlight > 0 && failedCount > 0) {
    summary = `${inFlight} in progress · ${failedCount} failed`
  } else if (inFlight > 0) {
    summary = `${inFlight} document${inFlight !== 1 ? 's' : ''} in progress`
  } else if (failedCount > 0) {
    summary = `${failedCount} failed job${failedCount !== 1 ? 's' : ''}`
  } else {
    summary = 'Nothing in flight'
  }

  return (
    <div className="flex flex-col h-full">
      <div className="shrink-0 px-4 py-3.5 border-b border-surface-border">
        <p className="text-sm font-semibold text-ink">Activity</p>
        <p className="text-xs text-ink-muted mt-0.5">
          {summary}
          {modelName && inFlight > 0 && <span className="text-ink-faint"> · {modelName}</span>}
        </p>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-2 min-h-0">
        {rows.length === 0 ? (
          <p className="text-xs text-ink-faint text-center py-8">No active work.</p>
        ) : (
          rows.map((row, i) => (
            <ActivityRow key={row.jobId || `local-${i}`} row={row} onCancel={onCancel} />
          ))
        )}
      </div>

      <div className="shrink-0 px-4 py-3 border-t border-surface-border">
        <p className="text-xs text-ink-faint text-center">
          {failedCount > 0 ? 'Click × on a failed job to remove it' : 'Documents appear in the table when complete'}
        </p>
      </div>
    </div>
  )
}

// ─── Main export ─────────────────────────────────────────────────────────────

export default function RightContextPanel({
  activeDoc,
  files,
  uploadState,
  uploadStates,
  uploadError,
  modelName,
  onOpenPreview,
  onChat,
  onDownload,
  onDelete,
  onCancelJob,
  onStartNewExtraction,
  processingJobs = [],
  failedJobs = [],
  forceActivityView = false,
}) {
  const isUploading = uploadState === uploadStates?.UPLOADING
  const hasUploadError = uploadState === uploadStates?.ERROR
  const hasActivity =
    isUploading || hasUploadError || processingJobs.length > 0 || failedJobs.length > 0

  // Priority:
  //   1. User explicitly clicked the ACTIVE/FAILED stat → force Activity even
  //      if a document is selected. Falls through to TipsPanel if nothing.
  //   2. A document is currently selected → preview takes precedence.
  //   3. Any in-flight or failed work → Activity panel.
  //   4. Default → Tips panel (no third drop zone here; single entry point is
  //      the top extraction bar).
  const activityPanel = (
    <ActivityPanel
      uploadingFile={isUploading ? files?.[0] : null}
      modelName={modelName}
      processingJobs={processingJobs}
      failedJobs={failedJobs}
      onCancel={onCancelJob}
      uploadError={hasUploadError ? uploadError : null}
    />
  )

  let inner
  if (forceActivityView && hasActivity) {
    inner = activityPanel
  } else if (activeDoc) {
    inner = (
      <DocumentPreviewPanel
        doc={activeDoc}
        onOpenPreview={onOpenPreview}
        onChat={onChat}
        onDownload={onDownload}
        onDelete={onDelete}
        onStartNewExtraction={onStartNewExtraction}
      />
    )
  } else if (hasActivity) {
    inner = activityPanel
  } else {
    inner = <TipsPanel />
  }

  return (
    <div className="flex flex-col h-full border-l border-surface-border bg-surface/80">
      {inner}
    </div>
  )
}
