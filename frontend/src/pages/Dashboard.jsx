import { useEffect, useRef, useState, useMemo, useCallback } from 'react'
import {
  FileUp,
  Search,
  FileText,
  X as XIcon,
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import DocumentTable from '../components/documents/DocumentTable'
import SplitViewer from '../components/documents/SplitViewer'
import RightContextPanel from '../components/documents/RightContextPanel'
import BulkActionsBar from '../components/documents/BulkActionsBar'
import Pagination from '../components/documents/Pagination'
import EmptyState from '../components/ui/EmptyState'
import Button from '../components/ui/Button'
import DropZone from '../components/upload/DropZone'
import { useFileUpload } from '../hooks/useFileUpload'
import { useJobPolling } from '../hooks/useJobPolling'
import { useDocuments } from '../hooks/useDocuments'
import { useJobs } from '../context/JobContext'
import { useApp } from '../context/AppContext'
import { useToast } from '../context/ToastContext'
import { deleteJob, listJobs } from '../api/jobs'
import { AVAILABLE_MODELS } from '../api/models'

const TYPE_TABS = [
  { key: 'all',    label: 'All' },
  { key: 'pdf',    label: 'PDF' },
  { key: 'image',  label: 'Images' },
  { key: 'office', label: 'Office' },
]

// ─── Extraction Control Card ──────────────────────────────────────────────────

function isPdfFile(file) {
  return file?.name?.toLowerCase().endsWith('.pdf')
}

const STAT_CONFIGS = [
  { key: 'total',  label: 'Total',  color: 'text-ink',           title: 'All uploads this session' },
  { key: 'done',   label: 'Done',   color: 'text-emerald-400',   title: 'Completed extractions' },
  { key: 'active', label: 'Active', color: 'text-amber-400',     title: 'Click to see in-flight jobs' },
  { key: 'failed', label: 'Failed', color: 'text-red-400',       title: 'Click to see failed jobs' },
]

function ExtractionControlCard({
  files, state, STATES,
  addFiles, removeFile,
  modelId, setModelId,
  startPage, setStartPage,
  endPage, setEndPage,
  pageRangeError,
  onExtract,
  total, completed, processing, failed,
  onStatClick,
  dropZoneRef,
}) {
  const isLoading = state === STATES.UPLOADING || state === STATES.SUBMITTED
  const canExtract = files.length > 0 && !isLoading && !pageRangeError
  // Page range is meaningful only for PDFs. Hide the inputs entirely once the
  // user has picked files and none of them are PDFs, so the form doesn't lie.
  const showPageRange = files.length === 0 || files.some(isPdfFile)

  const STAT_VALUES = { total, done: completed, active: processing, failed }

  return (
    <div className="shrink-0 rounded-2xl border border-surface-border bg-surface-glass backdrop-blur-md shadow-card">
      {/* Top row: file upload area + stats */}
      <div className="flex items-start gap-4 px-4 pt-4 pb-3 border-b border-surface-border/60">
        <div className="flex-1 min-w-0">
          {files.length === 0 ? (
            <DropZone
              ref={dropZoneRef}
              onFiles={addFiles}
              size="medium"
              className="w-full"
            />
          ) : (
            <div className="flex flex-wrap items-center gap-1.5">
              {files.map((f, i) => (
                <span
                  key={`${f.name}-${i}`}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-surface-border bg-surface-muted px-2.5 py-1.5 text-xs font-medium text-ink"
                >
                  <FileText className="h-3 w-3 shrink-0 text-brand" />
                  <span className="max-w-[180px] truncate">{f.name}</span>
                  {state === STATES.FILES_SELECTED && (
                    <button
                      onClick={() => removeFile(i)}
                      aria-label={`Remove ${f.name}`}
                      className="ml-0.5 text-ink-faint hover:text-red-400 transition-colors"
                    >
                      <XIcon className="h-3 w-3" />
                    </button>
                  )}
                </span>
              ))}
              {/* Add-more affordance when files are already queued */}
              {state === STATES.FILES_SELECTED && (
                <DropZone onFiles={addFiles} size="compact" />
              )}
            </div>
          )}
        </div>

        {/* Stats — clickable buttons so users can drill into in-flight work */}
        <div className="hidden sm:flex items-center divide-x divide-surface-border shrink-0">
          {STAT_CONFIGS.map(({ key, label, color, title }) => {
            const value = STAT_VALUES[key]
            // ACTIVE and FAILED open the Activity panel filtered to their state;
            // disable the click when the count is zero so the button is inert.
            const drillable = key === 'active' || key === 'failed'
            const disabled = drillable && value === 0
            return (
              <button
                key={key}
                type="button"
                onClick={() => onStatClick?.(key)}
                disabled={disabled}
                title={title}
                className={`px-4 first:pl-0 last:pr-0 text-center rounded-md transition-colors ${
                  disabled
                    ? 'cursor-default'
                    : 'cursor-pointer hover:bg-surface-muted/40 focus:outline-none focus:ring-2 focus:ring-brand/30'
                }`}
              >
                <p className={`text-lg font-bold leading-none ${color}`}>{value}</p>
                <p className="text-[10px] text-ink-faint mt-0.5 uppercase tracking-wider">{label}</p>
              </button>
            )
          })}
        </div>
      </div>

      {/* Bottom row: model + pages + extract button */}
      <div className="flex items-center gap-2 px-4 py-3 flex-wrap">
        {/* Model selector */}
        <div className="flex items-center gap-2">
          <label className="text-xs text-ink-faint shrink-0 hidden sm:block">Model</label>
          <select
            value={modelId}
            onChange={(e) => setModelId(e.target.value)}
            aria-label="Extraction model"
            className="rounded-lg border border-surface-border bg-surface-muted px-2.5 py-1.5 text-xs text-ink focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/20 transition-all max-w-[200px]"
          >
            {AVAILABLE_MODELS.map((m) => (
              <option key={m.id} value={m.id}>{m.name}</option>
            ))}
          </select>
        </div>

        {showPageRange && (
          <>
            <div className="hidden sm:block h-4 w-px bg-surface-border/60 shrink-0" />

            {/* Page range — PDF-only; helper text clarifies blank = all pages */}
            <div className="flex items-center gap-1.5">
              <label
                className="text-xs text-ink-faint shrink-0 hidden sm:block"
                title="Leave blank to extract all pages"
              >
                Pages
              </label>
              <input
                type="number"
                min="1"
                placeholder="From"
                value={startPage}
                onChange={(e) => setStartPage(e.target.value)}
                aria-label="Start page (leave blank for all pages)"
                title="Leave blank to extract all pages"
                className="w-16 rounded-lg border border-surface-border bg-surface-muted px-2 py-1.5 text-xs text-ink focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/20 transition-all placeholder:text-ink-faint/50"
              />
              <span className="text-xs text-ink-faint">–</span>
              <input
                type="number"
                min="1"
                placeholder="To"
                value={endPage}
                onChange={(e) => setEndPage(e.target.value)}
                aria-label="End page (leave blank for all pages)"
                title="Leave blank to extract all pages"
                className="w-16 rounded-lg border border-surface-border bg-surface-muted px-2 py-1.5 text-xs text-ink focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/20 transition-all placeholder:text-ink-faint/50"
              />
            </div>
          </>
        )}

        {/* Extract button — pushed right. Inline status text removed; the right
            panel already surfaces upload/processing state with more detail. */}
        <div className="ml-auto flex items-center gap-2">
          <Button
            onClick={onExtract}
            disabled={!canExtract}
            loading={isLoading}
            className="py-1.5 px-4 text-xs whitespace-nowrap"
          >
            Extract documents
          </Button>
        </div>
      </div>

      {/* Validation errors */}
      {pageRangeError && (
        <p className="px-4 pb-3 -mt-1 text-xs text-red-400">{pageRangeError}</p>
      )}
    </div>
  )
}

// ─── Documents Toolbar ────────────────────────────────────────────────────────

function DocumentToolbar({ allDocuments, search, setSearch, typeFilter, setTypeFilter }) {
  return (
    <div className="shrink-0 flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-3">
      <div>
        <h2 className="text-base font-semibold text-ink">Documents</h2>
        {allDocuments.length > 0 && (
          <p className="text-xs text-ink-faint mt-0.5">
            {allDocuments.length} document{allDocuments.length !== 1 ? 's' : ''} processed
          </p>
        )}
      </div>

      <div className="flex items-center gap-2 flex-wrap">
        {/* Search */}
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-ink-faint pointer-events-none" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search documents…"
            aria-label="Search documents"
            className="w-52 rounded-xl border border-surface-border bg-surface-muted/60 py-1.5 pl-8 pr-8 text-sm text-ink placeholder:text-ink-faint focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/20"
          />
          {search && (
            <button
              onClick={() => setSearch('')}
              aria-label="Clear search"
              className="absolute right-2 top-1/2 -translate-y-1/2 text-ink-faint hover:text-ink transition-colors"
            >
              <XIcon className="h-3.5 w-3.5" />
            </button>
          )}
        </div>

        {/* Type filter — segmented control */}
        <div className="flex items-center rounded-xl border border-surface-border bg-surface-muted/40 p-0.5 gap-0.5">
          {TYPE_TABS.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setTypeFilter(tab.key)}
              className={`rounded-lg px-3 py-1 text-xs font-medium transition-all ${
                typeFilter === tab.key
                  ? 'bg-surface-subtle border border-surface-border text-ink shadow-sm'
                  : 'text-ink-faint hover:text-ink-muted'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}

// ─── Dashboard Page ───────────────────────────────────────────────────────────

export default function Dashboard() {
  const navigate = useNavigate()
  const { jobs, removeJob, updateJob } = useJobs()
  const { backendUrl } = useApp()
  const toast = useToast()
  const { documents, allDocuments, search, setSearch, typeFilter, setTypeFilter } = useDocuments()

  // Upload state
  const { files, state, error, lastJobId, addFiles, removeFile, upload, reset, STATES } =
    useFileUpload()
  const [modelId, setModelId] = useState(AVAILABLE_MODELS[0].id)
  const [startPage, setStartPage] = useState('')
  const [endPage, setEndPage] = useState('')

  // Pagination
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)

  // Selection
  const [selectedIds, setSelectedIds] = useState(new Set())

  // Page mode keeps the document list and full parser workspace separate.
  const [mode, setMode] = useState('dashboard')
  const [activeDoc, setActiveDoc] = useState(null)

  // Ref to the top-bar DropZone so the EmptyState "Upload documents" button
  // can trigger the real file picker instead of guessing via querySelector.
  const dropZoneRef = useRef(null)

  // When the user clicks the ACTIVE stat tile we force the right panel to show
  // the Activity panel even if a document is selected. Cleared whenever the
  // user picks a doc or there's no in-flight work.
  const [forceActivityView, setForceActivityView] = useState(false)

  // Page range validation
  const pageRangeError =
    startPage && endPage && Number(startPage) > Number(endPage)
      ? 'Start page cannot be greater than end page.'
      : null

  useJobPolling(lastJobId)

  useEffect(() => {
    document.title = 'Dashboard — Intelidoc'
  }, [])

  // One-shot reconcile on mount: the JobContext loads from sessionStorage,
  // which can be stale across backend restarts (e.g. a job we last saw as
  // "processing" may have been marked FAILED by the recovery sweep on startup).
  // Polling only watches the most recent upload, so without this the stale row
  // would spin forever. We refresh every locally-known non-terminal job once.
  const reconciledRef = useRef(false)
  useEffect(() => {
    if (reconciledRef.current) return
    reconciledRef.current = true
    const stale = jobs.filter(
      (j) => j.status === 'processing' || j.status === 'pending' || j.status === 'queued'
    )
    if (stale.length === 0) return
    ;(async () => {
      const fresh = await listJobs(backendUrl).catch(() => null)
      if (!Array.isArray(fresh)) return
      // Backend list endpoint already returns `job_id` (DB id renamed in JSON).
      const byId = new Map(fresh.map((j) => [j.job_id, j]))
      for (const local of stale) {
        const server = byId.get(local.job_id)
        if (!server) continue
        updateJob(local.job_id, {
          status: server.status,
          documents: server.documents || [],
          updated_at: server.updated_at,
          meta: server.meta,
        })
      }
    })()
    // Intentionally only run once on mount; subsequent updates flow through
    // useJobPolling for the current upload.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Toast on upload error (failed before backend even saw it).
  const notifiedUploadErrorRef = useRef(null)
  useEffect(() => {
    if (
      state === STATES.ERROR &&
      lastJobId &&
      notifiedUploadErrorRef.current !== lastJobId
    ) {
      notifiedUploadErrorRef.current = lastJobId
      toast.error(error || 'Upload failed. Please try again.', { title: 'Upload failed' })
    }
  }, [state, STATES, lastJobId, error, toast])

  // Clear the file list once upload finishes so the user can queue another
  // doc immediately. Page range & model stay sticky — same settings are likely
  // wanted for the next batch.
  const clearedFormRef = useRef(null)
  useEffect(() => {
    if (state === STATES.DONE && lastJobId && clearedFormRef.current !== lastJobId) {
      clearedFormRef.current = lastJobId
      reset()
    }
  }, [state, STATES, lastJobId, reset])

  // Toast when the BACKEND finishes — we watch jobs for the matching job to
  // enter a terminal status with documents populated. This is more reliable
  // than tying the toast to the upload state (the backend extraction happens
  // asynchronously after upload).
  //
  // Seed `notifiedJobsRef` with whatever was already terminal on mount so we
  // don't spam toasts for historical jobs on page reload — but unlike the old
  // 5-minute cutoff, jobs that finish *while the tab is open* always toast,
  // even if they were uploaded long ago.
  const notifiedJobsRef = useRef(null)
  if (notifiedJobsRef.current === null) {
    const seeded = new Set()
    for (const j of jobs) {
      if (j.status === 'completed' || j.status === 'failed') seeded.add(j.job_id)
    }
    notifiedJobsRef.current = seeded
  }
  useEffect(() => {
    for (const job of jobs) {
      if (notifiedJobsRef.current.has(job.job_id)) continue
      const isTerminalSuccess = job.status === 'completed' && job.documents?.length
      const isTerminalFailure = job.status === 'failed'
      if (!isTerminalSuccess && !isTerminalFailure) continue
      notifiedJobsRef.current.add(job.job_id)

      if (isTerminalFailure) {
        toast.error(`"${job.filename || 'Document'}" failed to extract.`, {
          title: 'Extraction failed',
        })
      } else {
        toast.success(`"${job.filename || 'Document'}" is ready to view.`, {
          title: 'Extraction complete',
          action: {
            label: 'View',
            onClick: () => {
              const doc = {
                ...job.documents[0],
                job_id: job.job_id,
                model_id: job.model_id,
                job_status: job.status,
                created_at: job.created_at,
              }
              setActiveDoc(doc)
              setMode('review')
            },
          },
        })
      }
    }
  }, [jobs, toast])

  // Reset page when filters change
  useEffect(() => {
    setPage(1)
  }, [search, typeFilter, pageSize])

  // Stats
  const total = jobs.length
  const completed = jobs.filter((j) => j.status === 'completed').length
  const processingJobs = useMemo(
    () =>
      jobs.filter(
        (j) => j.status === 'processing' || j.status === 'queued' || j.status === 'pending'
      ),
    [jobs]
  )
  const processing = processingJobs.length
  const failedJobs = useMemo(
    () => jobs.filter((j) => j.status === 'failed'),
    [jobs]
  )
  const failed = failedJobs.length

  // Drop the forced Activity view automatically when there's nothing in flight
  // AND no failed jobs to show. Failed jobs need the panel too so the user can
  // see / retry / delete them — otherwise the auto-reset would close the panel
  // immediately after a FAILED click since `processing === 0` for stale fails.
  useEffect(() => {
    if (
      forceActivityView &&
      processing === 0 &&
      failed === 0 &&
      state !== STATES.UPLOADING &&
      state !== STATES.ERROR
    ) {
      setForceActivityView(false)
    }
  }, [forceActivityView, processing, failed, state, STATES])

  // Paginated documents
  const paginatedDocs = useMemo(() => {
    const start = (page - 1) * pageSize
    return documents.slice(start, start + pageSize)
  }, [documents, page, pageSize])

  const activeDocId = activeDoc?.id ?? activeDoc?.job_id ?? null
  const currentModelName = AVAILABLE_MODELS.find((m) => m.id === modelId)?.name || modelId

  // ── Handlers ──

  const handleExtract = () => {
    const sp = startPage ? Number(startPage) : null
    const ep = endPage ? Number(endPage) : null
    upload(modelId, sp, ep)
  }

  // Row click goes straight into the SplitViewer — no intermediate preview
  // pane. The hover eye icon (onPreview) uses the same handler for parity.
  const handleOpenPreview = useCallback((doc) => {
    if (doc) setActiveDoc(doc)
    setMode('review')
  }, [])

  // Closing the viewer returns to the dashboard list and drops the active doc
  // so the right pane goes back to its idle/activity state instead of showing
  // the doc the user just closed.
  const handleCloseViewer = useCallback(() => {
    setMode('dashboard')
    setActiveDoc(null)
  }, [])

  // "Start new extraction" — clears active doc and upload state so the user
  // can drop fresh files. Used from both the side panel and the SplitViewer.
  const handleStartNewExtraction = useCallback(() => {
    setActiveDoc(null)
    setMode('dashboard')
    reset()
    setStartPage('')
    setEndPage('')
  }, [reset])

  const handleChat = useCallback(
    (doc) => {
      navigate('/chat', { state: { groundingDoc: doc } })
    },
    [navigate]
  )

  const handleDownloadDoc = useCallback((doc) => {
    const content = doc.content_text || ''
    const blob = new Blob([content], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${doc.filename || 'document'}.txt`
    a.click()
    URL.revokeObjectURL(url)
  }, [])

  const handleDeleteDoc = useCallback(
    async (doc) => {
      try {
        await deleteJob(doc.job_id, backendUrl)
        removeJob(doc.job_id)
        if (activeDoc?.job_id === doc.job_id) {
          setActiveDoc(null)
          setMode('dashboard')
        }
      } catch {
        // SplitViewer has its own error display; here we just swallow
      }
    },
    [backendUrl, removeJob, activeDoc]
  )

  const handleToggleSelect = useCallback((docId) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(docId)) next.delete(docId)
      else next.add(docId)
      return next
    })
  }, [])

  const handleToggleSelectAll = useCallback(() => {
    const allIds = paginatedDocs.map((d) => d.id ?? d.job_id)
    const allSelected = allIds.every((id) => selectedIds.has(id))
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (allSelected) allIds.forEach((id) => next.delete(id))
      else allIds.forEach((id) => next.add(id))
      return next
    })
  }, [paginatedDocs, selectedIds])

  const handleBulkDownload = useCallback(() => {
    documents
      .filter((d) => selectedIds.has(d.id ?? d.job_id))
      .forEach((doc) => handleDownloadDoc(doc))
  }, [documents, selectedIds, handleDownloadDoc])

  // Bulk delete: fire all DELETEs in parallel, prune local state regardless of
  // server outcome (404 means it's already gone, which is what we wanted), and
  // surface a single summary toast at the end.
  const handleBulkDelete = useCallback(async () => {
    const targets = documents.filter((d) => selectedIds.has(d.id ?? d.job_id))
    if (targets.length === 0) return

    const results = await Promise.allSettled(
      targets.map((d) => deleteJob(d.job_id, backendUrl))
    )
    for (const d of targets) removeJob(d.job_id)

    // Close the side preview if the open doc was deleted out from under it.
    const activeKey = activeDoc?.id ?? activeDoc?.job_id
    if (activeKey && selectedIds.has(activeKey)) {
      setActiveDoc(null)
      setMode('dashboard')
    }
    setSelectedIds(new Set())

    const failed = results.filter((r) => r.status === 'rejected').length
    if (failed === 0) {
      toast.success(`Deleted ${targets.length} document${targets.length !== 1 ? 's' : ''}.`)
    } else {
      toast.error(`Deleted ${targets.length - failed} of ${targets.length}. ${failed} failed.`)
    }
  }, [documents, selectedIds, backendUrl, removeJob, activeDoc, toast])

  const handleDeselectAll = useCallback(() => setSelectedIds(new Set()), [])

  // Opens the real file picker attached to the top-bar DropZone. Used by the
  // empty state and any other "Upload documents" affordance so we don't
  // depend on a global querySelector picking the right hidden input.
  const handleRequestUpload = useCallback(() => {
    dropZoneRef.current?.openFilePicker()
  }, [])

  // Cancel an in-flight job from the Activity panel. Calls DELETE on the
  // backend, then drops it from local state so the row disappears immediately.
  const handleCancelJob = useCallback(
    async (jobId) => {
      try {
        await deleteJob(jobId, backendUrl)
      } catch {
        // Already missing on the server is fine — we still want to clean local
        // state. Other errors fall through; the row will reappear on next poll.
      }
      removeJob(jobId)
    },
    [backendUrl, removeJob]
  )

  // Stat tile clicks. ACTIVE and FAILED open the Activity panel; TOTAL/DONE
  // clear any overrides. We don't add per-status table filters yet.
  const handleStatClick = useCallback(
    (key) => {
      if (key === 'active') {
        if (processing > 0 || state === STATES.UPLOADING || state === STATES.ERROR) {
          setActiveDoc(null)
          setForceActivityView(true)
        }
      } else if (key === 'failed') {
        if (failed > 0) {
          setActiveDoc(null)
          setForceActivityView(true)
        }
      } else {
        setForceActivityView(false)
      }
    },
    [processing, failed, state, STATES]
  )

  // Picking a document explicitly should always take you to its preview, even
  // if the user had previously forced the Activity view.
  useEffect(() => {
    if (activeDoc) setForceActivityView(false)
  }, [activeDoc])

  return (
    <div className="flex h-[calc(100vh-4rem)] gap-3 min-h-0 animate-slide-up-fade">
      {mode === 'review' && activeDoc ? (
        <div className="flex-1 min-w-0 min-h-0">
          <SplitViewer
            doc={activeDoc}
            documents={allDocuments}
            isOpen
            onClose={handleCloseViewer}
            onSelectDoc={setActiveDoc}
            onStartNewExtraction={handleStartNewExtraction}
          />
        </div>
      ) : (
        <>

      {/* ── Main workspace ─────────────────────────────────────────────────── */}
      <div className="flex flex-col flex-1 min-w-0 min-h-0 gap-3">

        {/* Extraction Control Card */}
        <ExtractionControlCard
          files={files}
          state={state}
          STATES={STATES}
          addFiles={addFiles}
          removeFile={removeFile}
          modelId={modelId}
          setModelId={setModelId}
          startPage={startPage}
          setStartPage={setStartPage}
          endPage={endPage}
          setEndPage={setEndPage}
          pageRangeError={pageRangeError}
          onExtract={handleExtract}
          total={total}
          completed={completed}
          processing={processing}
          failed={failed}
          onStatClick={handleStatClick}
          dropZoneRef={dropZoneRef}
        />

        {/* Documents section */}
        <div className="flex flex-col flex-1 min-h-0">
          <DocumentToolbar
            allDocuments={allDocuments}
            search={search}
            setSearch={setSearch}
            typeFilter={typeFilter}
            setTypeFilter={setTypeFilter}
          />

          {/* Table or empty state */}
          {allDocuments.length === 0 ? (
            // If a job is already in flight (uploading or processing) but no
            // documents have completed yet, don't pretend the dashboard is
            // empty — that contradicts the ACTIVE counter. Point users at the
            // Activity panel instead.
            jobs.length > 0 ? (
              <EmptyState
                icon={FileUp}
                heading="First extraction in progress"
                subtext="Documents will appear here as soon as the extraction completes. Click the ACTIVE counter to see live status."
                actionLabel="View activity"
                onAction={() => handleStatClick('active')}
              />
            ) : (
              <EmptyState
                icon={FileUp}
                heading="No documents yet"
                subtext="Upload PDF, DOCX, XLSX, PPTX, PNG, or JPG files to start extracting."
                actionLabel="Upload documents"
                onAction={handleRequestUpload}
              />
            )
          ) : (
            <div className="flex-1 flex flex-col min-h-0">
              <div className="flex-1 overflow-auto">
                <DocumentTable
                  documents={paginatedDocs}
                  activeDocId={activeDocId}
                  selectedIds={selectedIds}
                  onSelectDoc={handleOpenPreview}
                  onToggleSelect={handleToggleSelect}
                  onToggleSelectAll={handleToggleSelectAll}
                  onPreview={handleOpenPreview}
                  onChat={handleChat}
                  onDownload={handleDownloadDoc}
                  onDelete={handleDeleteDoc}
                  isPaneOpen={false}
                />
              </div>

              {documents.length > pageSize && (
                <div className="shrink-0 border-t border-surface-border pt-2">
                  <Pagination
                    page={page}
                    pageSize={pageSize}
                    total={documents.length}
                    onPageChange={setPage}
                    onPageSizeChange={(size) => {
                      setPageSize(size)
                      setPage(1)
                    }}
                  />
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* ── Right context panel ────────────────────────────────────────────── */}
      <div className="hidden xl:flex shrink-0 flex-col min-h-0 w-[360px] 2xl:w-[384px]">
        <RightContextPanel
          activeDoc={activeDoc}
          files={files}
          uploadState={state}
          uploadStates={STATES}
          uploadError={state === STATES.ERROR ? { message: error, filename: files?.[0]?.name } : null}
          modelName={currentModelName}
          onOpenPreview={handleOpenPreview}
          onChat={handleChat}
          onDownload={handleDownloadDoc}
          onDelete={handleDeleteDoc}
          onCancelJob={handleCancelJob}
          onStartNewExtraction={handleStartNewExtraction}
          processingJobs={processingJobs}
          failedJobs={failedJobs}
          forceActivityView={forceActivityView}
        />
      </div>

      {/* Bulk Actions */}
      <BulkActionsBar
        count={selectedIds.size}
        onDownload={handleBulkDownload}
        onDelete={handleBulkDelete}
        onDeselect={handleDeselectAll}
      />
        </>
      )}
    </div>
  )
}
