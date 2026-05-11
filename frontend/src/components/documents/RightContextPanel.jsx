import { useState } from 'react'
import { Eye, MessageSquare, Download, Trash2, Loader2, Upload, Plus } from 'lucide-react'
import Badge from '../ui/Badge'
import DropZone from '../upload/DropZone'

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

// ─── Upload Panel ────────────────────────────────────────────────────────────

function UploadPanel({ onFiles }) {
  return (
    <div className="flex flex-col h-full">
      <div className="shrink-0 px-4 py-3.5 border-b border-surface-border">
        <p className="text-sm font-semibold text-ink">Upload documents</p>
        <p className="text-xs text-ink-muted mt-0.5">Drag files or browse to add</p>
      </div>

      <div className="flex-1 flex flex-col justify-center gap-4 p-4">
        <DropZone onFiles={onFiles} />

        <div className="text-center space-y-0.5">
          <p className="text-xs text-ink-faint">PDF, DOCX, XLSX, PPTX, PNG, JPG</p>
          <p className="text-xs text-ink-faint">Maximum 50 MB per file</p>
        </div>

        <div className="rounded-xl bg-brand/5 border border-brand/15 p-3">
          <p className="text-xs text-brand/70 leading-relaxed">
            After upload, choose a model and click{' '}
            <span className="font-semibold text-brand">Extract documents</span> to process.
          </p>
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

// ─── Extraction Progress Panel ────────────────────────────────────────────────

function ExtractionProgressPanel({ files, modelName, state, STATES }) {
  const isUploading = state === STATES.UPLOADING
  const isSubmitted = state === STATES.SUBMITTED
  const isDone = state === STATES.DONE
  const isError = state === STATES.ERROR

  const currentFile = files?.[0]?.name || 'document'

  const statusText = isUploading
    ? 'Uploading file…'
    : isSubmitted
      ? 'Processing with AI model…'
      : isDone
        ? 'Extraction complete'
        : 'Extraction failed'

  return (
    <div className="flex flex-col h-full">
      <div className="shrink-0 px-4 py-3.5 border-b border-surface-border">
        <p className="text-sm font-semibold text-ink">
          {isDone ? 'Extraction complete' : isError ? 'Extraction failed' : 'Extracting document…'}
        </p>
        {modelName && <p className="text-xs text-ink-muted mt-0.5">{modelName}</p>}
      </div>

      <div className="flex-1 flex flex-col items-center justify-center gap-5 p-6">
        {/* Status icon */}
        <div
          className={`flex h-16 w-16 items-center justify-center rounded-2xl ${
            isDone
              ? 'bg-emerald-400/10 border border-emerald-400/20'
              : isError
                ? 'bg-red-400/10 border border-red-400/20'
                : 'bg-amber-400/10 border border-amber-400/20'
          }`}
        >
          {isDone ? (
            <Upload className="h-7 w-7 text-emerald-400" />
          ) : isError ? (
            <Upload className="h-7 w-7 text-red-400" />
          ) : (
            <Loader2 className="h-7 w-7 text-amber-300 animate-spin" />
          )}
        </div>

        {/* File name */}
        <div className="text-center max-w-full px-2">
          <p className="text-sm font-medium text-ink truncate" title={currentFile}>
            {currentFile}
          </p>
          <p className="text-xs text-ink-faint mt-1">{statusText}</p>
        </div>

        {/* Progress bar */}
        {(isUploading || isSubmitted) && (
          <div className="w-full max-w-[160px]">
            <div className="h-1 bg-surface-muted rounded-full overflow-hidden">
              <div
                className="h-full bg-amber-400 rounded-full transition-all duration-700"
                style={{ width: isSubmitted ? '75%' : '35%' }}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// ─── Active Jobs Panel ────────────────────────────────────────────────────────

function ActiveJobsPanel({ jobs }) {
  return (
    <div className="flex flex-col h-full">
      <div className="shrink-0 px-4 py-3.5 border-b border-surface-border">
        <p className="text-sm font-semibold text-ink">Processing documents</p>
        <p className="text-xs text-ink-muted mt-0.5">
          {jobs.length} document{jobs.length !== 1 ? 's' : ''} in progress
        </p>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-2 min-h-0">
        {jobs.map((job) => (
          <div
            key={job.job_id}
            className="flex items-center gap-3 rounded-xl border border-surface-border bg-surface-muted/40 px-3 py-3"
          >
            <Loader2 className="h-4 w-4 shrink-0 text-amber-400 animate-spin" />
            <div className="min-w-0 flex-1">
              <p className="text-xs font-medium text-ink truncate">
                {job.filename || job.job_id}
              </p>
              <p className="text-[11px] text-ink-faint mt-0.5 capitalize">{job.status}</p>
            </div>
          </div>
        ))}
      </div>

      <div className="shrink-0 px-4 py-3 border-t border-surface-border">
        <p className="text-xs text-ink-faint text-center">
          Documents appear in the table when complete
        </p>
      </div>
    </div>
  )
}

// ─── Main export ─────────────────────────────────────────────────────────────

export default function RightContextPanel({
  activeDoc,
  files,
  onFiles,
  uploadState,
  uploadStates,
  modelName,
  onOpenPreview,
  onChat,
  onDownload,
  onDelete,
  onStartNewExtraction,
  processingJobs = [],
}) {
  const isExtracting =
    uploadState === uploadStates?.UPLOADING ||
    uploadState === uploadStates?.SUBMITTED ||
    uploadState === uploadStates?.ERROR

  let inner
  if (isExtracting) {
    inner = (
      <ExtractionProgressPanel
        files={files}
        modelName={modelName}
        state={uploadState}
        STATES={uploadStates}
      />
    )
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
  } else if (processingJobs.length > 0) {
    inner = <ActiveJobsPanel jobs={processingJobs} />
  } else {
    inner = <UploadPanel onFiles={onFiles} />
  }

  return (
    <div className="flex flex-col h-full border-l border-surface-border bg-surface/80">
      {inner}
    </div>
  )
}
