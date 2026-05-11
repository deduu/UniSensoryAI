import { useEffect, useRef, useState, useMemo, useCallback } from 'react'
import {
  FileUp,
  Search,
  FileText,
  X as XIcon,
  Loader2,
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
import { deleteJob } from '../api/jobs'
import { AVAILABLE_MODELS } from '../api/models'

const TYPE_TABS = [
  { key: 'all',    label: 'All' },
  { key: 'pdf',    label: 'PDF' },
  { key: 'image',  label: 'Images' },
  { key: 'office', label: 'Office' },
]

// ─── Extraction Control Card ──────────────────────────────────────────────────

function ExtractionControlCard({
  files, state, error, STATES,
  addFiles, removeFile,
  modelId, setModelId,
  startPage, setStartPage,
  endPage, setEndPage,
  pageRangeError,
  onExtract,
  total, completed, processing,
}) {
  const isLoading = state === STATES.UPLOADING || state === STATES.SUBMITTED
  const canExtract = files.length > 0 && !isLoading && !pageRangeError

  return (
    <div className="shrink-0 rounded-2xl border border-surface-border bg-surface-glass backdrop-blur-md shadow-card">
      {/* Top row: file upload area + stats */}
      <div className="flex items-start gap-4 px-4 pt-4 pb-3 border-b border-surface-border/60">
        <div className="flex-1 min-w-0">
          {files.length === 0 ? (
            <DropZone onFiles={addFiles} compact className="w-full justify-center py-2.5" />
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
                <DropZone onFiles={addFiles} compact />
              )}
            </div>
          )}
        </div>

        {/* Stats */}
        <div className="hidden sm:flex items-center divide-x divide-surface-border shrink-0">
          {[
            { label: 'Total',  value: total,      color: 'text-ink' },
            { label: 'Done',   value: completed,  color: 'text-emerald-400' },
            { label: 'Active', value: processing, color: 'text-amber-400' },
          ].map(({ label, value, color }) => (
            <div key={label} className="px-4 first:pl-0 last:pr-0 text-center">
              <p className={`text-lg font-bold leading-none ${color}`}>{value}</p>
              <p className="text-[10px] text-ink-faint mt-0.5 uppercase tracking-wider">{label}</p>
            </div>
          ))}
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

        <div className="hidden sm:block h-4 w-px bg-surface-border/60 shrink-0" />

        {/* Page range */}
        <div className="flex items-center gap-1.5">
          <label className="text-xs text-ink-faint shrink-0 hidden sm:block">Pages</label>
          <input
            type="number"
            min="1"
            placeholder="From"
            value={startPage}
            onChange={(e) => setStartPage(e.target.value)}
            aria-label="Start page"
            className="w-16 rounded-lg border border-surface-border bg-surface-muted px-2 py-1.5 text-xs text-ink focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/20 transition-all placeholder:text-ink-faint/50"
          />
          <span className="text-xs text-ink-faint">–</span>
          <input
            type="number"
            min="1"
            placeholder="To"
            value={endPage}
            onChange={(e) => setEndPage(e.target.value)}
            aria-label="End page"
            className="w-16 rounded-lg border border-surface-border bg-surface-muted px-2 py-1.5 text-xs text-ink focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/20 transition-all placeholder:text-ink-faint/50"
          />
        </div>

        {/* Extract button — pushed right */}
        <div className="ml-auto flex items-center gap-2">
          {/* Inline upload progress text */}
          {(state === STATES.UPLOADING || state === STATES.SUBMITTED || state === STATES.DONE || state === STATES.ERROR) && (
            <span className={`text-xs flex items-center gap-1.5 ${
              state === STATES.ERROR  ? 'text-red-400' :
              state === STATES.DONE   ? 'text-emerald-400' :
              'text-amber-400'
            }`}>
              {(state === STATES.UPLOADING || state === STATES.SUBMITTED) && (
                <Loader2 className="h-3 w-3 animate-spin shrink-0" />
              )}
              {state === STATES.UPLOADING ? 'Uploading…' :
               state === STATES.SUBMITTED ? 'Processing…' :
               state === STATES.DONE      ? 'Done' :
               error || 'Error'}
            </span>
          )}

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
  const { jobs, removeJob } = useJobs()
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

  // Page range validation
  const pageRangeError =
    startPage && endPage && Number(startPage) > Number(endPage)
      ? 'Start page cannot be greater than end page.'
      : null

  useJobPolling(lastJobId)

  useEffect(() => {
    document.title = 'Dashboard — Intelidoc'
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

  // Clear the upload form once upload finishes so the user can queue another
  // doc immediately. (We notify them about job completion separately, below.)
  const clearedFormRef = useRef(null)
  useEffect(() => {
    if (state === STATES.DONE && lastJobId && clearedFormRef.current !== lastJobId) {
      clearedFormRef.current = lastJobId
      reset()
      setStartPage('')
      setEndPage('')
    }
  }, [state, STATES, lastJobId, reset])

  // Toast when the BACKEND finishes — we watch jobs for the matching job to
  // enter a terminal status with documents populated. This is more reliable
  // than tying the toast to the upload state (the backend extraction happens
  // asynchronously after upload).
  const notifiedJobsRef = useRef(new Set())
  useEffect(() => {
    for (const job of jobs) {
      if (notifiedJobsRef.current.has(job.job_id)) continue
      const isTerminalSuccess = job.status === 'completed' && job.documents?.length
      const isTerminalFailure = job.status === 'failed'
      if (!isTerminalSuccess && !isTerminalFailure) continue
      notifiedJobsRef.current.add(job.job_id)

      // Skip toasts for pre-existing jobs loaded on page mount — we only want
      // to notify about jobs that completed *during* this session.
      const ageMs = job.created_at ? Date.now() - new Date(job.created_at).getTime() : Infinity
      if (ageMs > 5 * 60 * 1000) continue

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
  const processing = jobs.filter(
    (j) => j.status === 'processing' || j.status === 'queued' || j.status === 'pending'
  ).length

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

  // Single click on a row fills the side panel with preview. To expand into
  // the full SplitViewer, user clicks the eye icon (row hover action) or the
  // "Open preview" button in the side panel — handleOpenPreview.
  const handleSelectDoc = useCallback((doc) => {
    setActiveDoc(doc)
  }, [])

  const handleOpenPreview = useCallback((doc) => {
    if (doc) setActiveDoc(doc)
    setMode('review')
  }, [])

  const handleCloseViewer = useCallback(() => {
    setMode('dashboard')
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

  const handleDeselectAll = useCallback(() => setSelectedIds(new Set()), [])

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
          error={error}
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
            <EmptyState
              icon={FileUp}
              heading="No documents yet"
              subtext="Upload PDF, DOCX, XLSX, PPTX, PNG, or JPG files to start extracting."
              actionLabel="Upload documents"
              onAction={() => document.querySelector('input[type="file"]')?.click()}
            />
          ) : (
            <div className="flex-1 flex flex-col min-h-0">
              <div className="flex-1 overflow-auto">
                <DocumentTable
                  documents={paginatedDocs}
                  activeDocId={activeDocId}
                  selectedIds={selectedIds}
                  onSelectDoc={handleSelectDoc}
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
          onFiles={addFiles}
          uploadState={state}
          uploadStates={STATES}
          modelName={currentModelName}
          onOpenPreview={handleOpenPreview}
          onChat={handleChat}
          onDownload={handleDownloadDoc}
          onDelete={handleDeleteDoc}
          onStartNewExtraction={handleStartNewExtraction}
          processingJobs={jobs.filter((j) =>
            j.status === 'processing' || j.status === 'pending' || j.status === 'queued'
          )}
        />
      </div>

      {/* Bulk Actions */}
      <BulkActionsBar
        count={selectedIds.size}
        onDownload={handleBulkDownload}
        onDeselect={handleDeselectAll}
      />
        </>
      )}
    </div>
  )
}
