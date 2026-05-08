import { CheckCircle2, AlertCircle, Loader2 } from 'lucide-react'

export default function UploadProgress({ state, error, STATES, inline = false }) {
  if (state === STATES.IDLE || state === STATES.FILES_SELECTED) return null

  if (inline) {
    return (
      <span className="inline-flex items-center gap-1.5 text-xs text-ink-muted">
        {state === STATES.UPLOADING && (
          <><Loader2 className="h-3.5 w-3.5 animate-spin text-brand" /><span>Uploading…</span></>
        )}
        {state === STATES.SUBMITTED && (
          <><Loader2 className="h-3.5 w-3.5 animate-spin text-amber-400" /><span className="text-amber-400">Processing…</span></>
        )}
        {state === STATES.DONE && (
          <><CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" /><span className="text-emerald-400">Done</span></>
        )}
        {state === STATES.ERROR && (
          <><AlertCircle className="h-3.5 w-3.5 text-red-400" /><span className="text-red-400">{error || 'Failed'}</span></>
        )}
      </span>
    )
  }

  return (
    <div className="rounded-lg border border-surface-border bg-surface-subtle p-4">
      <div className="flex items-center gap-3">
        {state === STATES.UPLOADING && (
          <>
            <Loader2 className="h-5 w-5 animate-spin text-brand" />
            <span className="text-sm font-medium text-ink">Uploading...</span>
          </>
        )}
        {state === STATES.SUBMITTED && (
          <>
            <Loader2 className="h-5 w-5 animate-spin text-amber-500" />
            <span className="text-sm font-medium text-ink">Processing document...</span>
          </>
        )}
        {state === STATES.DONE && (
          <>
            <CheckCircle2 className="h-5 w-5 text-emerald-500" />
            <span className="text-sm font-medium text-ink">All files submitted for processing</span>
          </>
        )}
        {state === STATES.ERROR && (
          <>
            <AlertCircle className="h-5 w-5 text-red-500" />
            <span className="text-sm font-medium text-red-600">{error || 'Upload failed'}</span>
          </>
        )}
      </div>
    </div>
  )
}
