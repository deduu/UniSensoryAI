import { useCallback, useDeferredValue, useEffect, useMemo, useRef, useState } from 'react'
import {
  AlertCircle,
  Check,
  ChevronLeft,
  ChevronRight,
  Copy,
  Cpu,
  Download,
  Eye,
  EyeOff,
  Files,
  FileText,
  Hash,
  MessageSquare,
  Plus,
  RotateCcw,
  Search,
  Trash2,
  X,
  ZoomIn,
  ZoomOut,
} from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { useNavigate } from 'react-router-dom'
import remarkGfm from 'remark-gfm'
import { Document, Page, pdfjs } from 'react-pdf'
import 'react-pdf/dist/Page/AnnotationLayer.css'
import 'react-pdf/dist/Page/TextLayer.css'
import { deleteJob, retryJob } from '../../api/jobs'
import { useApp } from '../../context/AppContext'
import { useJobs } from '../../context/JobContext'
import PolicyReviewPanel from './PolicyReviewPanel'
import Badge from '../ui/Badge'

// Vite-bundled pdf.js worker — required by react-pdf so parsing happens off the main thread.
pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString()

const TABS = [
  { key: 'content', label: 'Content' },
  { key: 'policy', label: 'Policy' },
  { key: 'metadata', label: 'Metadata' },
  { key: 'raw', label: 'Raw JSON' },
]

const IMAGE_EXTS = new Set(['png', 'jpg', 'jpeg', 'webp', 'gif'])
const OFFICE_EXTS = new Set(['docx', 'pptx', 'xlsx'])
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i

function IconButton({ label, onClick, children, active = false, danger = false, disabled = false }) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex h-8 w-8 items-center justify-center rounded-lg border transition-colors disabled:opacity-50 ${
        danger && active
          ? 'border-red-400/30 bg-red-400/10 text-red-400 hover:bg-red-400/15'
          : danger
          ? 'border-surface-border bg-surface-muted text-ink-muted hover:bg-red-400/10 hover:text-red-400'
          : active
            ? 'border-brand/25 bg-brand/10 text-brand hover:bg-brand/15'
            : 'border-surface-border bg-surface-muted text-ink-muted hover:bg-surface-subtle hover:text-ink'
      }`}
    >
      {children}
    </button>
  )
}

function getExt(filename) {
  return filename?.split('.').pop()?.toLowerCase() || ''
}

function getFriendlyName(doc) {
  const filename = doc.filename || ''
  const bare = filename.replace(/\.[^/.]+$/, '')
  if (!bare || UUID_RE.test(bare)) return IMAGE_EXTS.has(getExt(filename)) ? 'Image extraction' : 'Document'
  return bare
}

function formatSize(bytes) {
  if (!bytes) return '-'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1048576).toFixed(1)} MB`
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function escapeHtml(value) {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function getUploadedContradictionClauses(policyReview) {
  const clauses = []
  for (const finding of policyReview?.findings || []) {
    for (const clause of finding.clauses || []) {
      if (clause.source !== 'uploaded_document' || !clause.text?.trim()) continue
      if (!clauses.some((item) => item.text === clause.text)) clauses.push(clause)
    }
  }
  return clauses
}

function injectHighlightsIntoHtml(html, clauses, zoom = 100) {
  if (!html) return html
  let highlighted = html
  const sortedClauses = [...clauses].sort((a, b) => b.text.length - a.text.length)
  for (const clause of sortedClauses) {
    const text = clause.text.trim()
    if (text.length < 12) continue
    const pattern = new RegExp(escapeRegExp(escapeHtml(text)), 'gi')
    highlighted = highlighted.replace(
      pattern,
      (match) => `<mark class="policy-contradiction-highlight">${match}</mark>`
    )
  }
  return highlighted.replace(
    '</head>',
    `<style>
      body {
        zoom: ${zoom / 100};
      }
      .policy-contradiction-highlight {
        background: rgba(245, 158, 11, 0.38);
        color: inherit;
        outline: 2px solid rgba(248, 113, 113, 0.65);
        border-radius: 3px;
        padding: 0 2px;
      }
    </style></head>`
  )
}

// react-pdf renders each page as a <canvas> inside our DOM, so the host page
// can observe and drive scroll position — unlike a browser-native PDF iframe.
function PdfViewer({ src, zoom, scrollRef, fileLabel }) {
  const [numPages, setNumPages] = useState(0)
  const [pageWidth, setPageWidth] = useState(800)
  const containerRef = useRef(null)

  // Measure the container width so pages render at the right size for the
  // current split width. Re-measure on resize.
  useEffect(() => {
    const el = containerRef.current
    if (!el) return undefined
    const update = () => {
      const w = el.clientWidth
      if (w > 0) setPageWidth(Math.max(320, w - 32))
    }
    update()
    const ro = new ResizeObserver(update)
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const setRefs = useCallback((node) => {
    containerRef.current = node
    if (typeof scrollRef === 'function') scrollRef(node)
    else if (scrollRef) scrollRef.current = node
  }, [scrollRef])

  return (
    <div ref={setRefs} className="h-full w-full overflow-auto bg-surface-subtle/40 px-4 py-4">
      <Document
        file={src}
        onLoadSuccess={({ numPages: n }) => setNumPages(n)}
        loading={<div className="py-12 text-center text-sm text-ink-muted">Loading PDF…</div>}
        error={<div className="py-12 text-center text-sm text-red-400">Failed to render PDF.</div>}
        className="flex flex-col items-center gap-4"
      >
        {Array.from({ length: numPages }, (_, i) => (
          <Page
            key={`${fileLabel}-${i + 1}`}
            pageNumber={i + 1}
            width={pageWidth * (zoom / 100)}
            renderAnnotationLayer={false}
            renderTextLayer
            className="shadow-card"
          />
        ))}
      </Document>
    </div>
  )
}

function OriginalPreview({ doc, backendUrl, policyReview, scrollRef }) {
  const [state, setState] = useState('loading')
  const [objectUrl, setObjectUrl] = useState(null)
  const [htmlPreview, setHtmlPreview] = useState('')
  const [retryCount, setRetryCount] = useState(0)
  const [zoom, setZoom] = useState(100)

  const ext = getExt(doc.filename)
  const isOffice = OFFICE_EXTS.has(ext)
  const canPreview = ext === 'pdf' || IMAGE_EXTS.has(ext) || isOffice
  const fileUrl = doc.job_id ? `${backendUrl}/v1/jobs/${doc.job_id}/file` : null
  const previewUrl = doc.job_id
    ? `${backendUrl}/v1/jobs/${doc.job_id}${isOffice ? '/preview/html' : '/file'}`
    : null

  const startPage = doc.meta?.start_page ?? null
  const endPage = doc.meta?.end_page ?? null
  const hasPageRange = startPage != null || endPage != null
  const contradictionClauses = useMemo(() => getUploadedContradictionClauses(policyReview), [policyReview])
  const firstContradictionText = contradictionClauses[0]?.text?.trim()
  const highlightedHtmlPreview = useMemo(
    () => injectHighlightsIntoHtml(htmlPreview, contradictionClauses, zoom),
    [htmlPreview, contradictionClauses, zoom]
  )

  useEffect(() => {
    if (!canPreview || !previewUrl) {
      setState('error')
      return undefined
    }

    const controller = new AbortController()
    let nextObjectUrl = null
    setState('loading')
    setObjectUrl(null)
    setHtmlPreview('')

    fetch(previewUrl, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error('Preview unavailable')
        if (isOffice) return response.text()
        const contentType = response.headers.get('content-type') || ''
        if (contentType.includes('application/json')) throw new Error('Preview unavailable')
        return response.blob()
      })
      .then((payload) => {
        if (isOffice) {
          setHtmlPreview(payload)
        } else {
          nextObjectUrl = URL.createObjectURL(payload)
          setObjectUrl(nextObjectUrl)
        }
        setState('ok')
      })
      .catch((error) => {
        if (error.name !== 'AbortError') setState('error')
      })

    return () => {
      controller.abort()
      if (nextObjectUrl) URL.revokeObjectURL(nextObjectUrl)
    }
  }, [previewUrl, retryCount, isOffice])

  const zoomOut = () => setZoom((value) => Math.max(50, value - 10))
  const zoomIn = () => setZoom((value) => Math.min(200, value + 10))
  const resetZoom = () => setZoom(100)

  const zoomControls = (
    <div className="flex items-center gap-1 rounded-lg border border-surface-border bg-surface-muted px-1 py-1">
      <IconButton label="Zoom out original preview" onClick={zoomOut} disabled={zoom <= 50}>
        <ZoomOut className="h-4 w-4" />
      </IconButton>
      <button
        type="button"
        onClick={resetZoom}
        className="h-8 min-w-12 rounded-md px-2 text-xs font-medium text-ink-muted transition-colors hover:bg-surface-subtle hover:text-ink"
        title="Reset zoom"
      >
        {zoom}%
      </button>
      <IconButton label="Zoom in original preview" onClick={zoomIn} disabled={zoom >= 200}>
        <ZoomIn className="h-4 w-4" />
      </IconButton>
    </div>
  )

  if (!canPreview || state === 'error') {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-4 px-8 text-center">
        <div className="flex h-16 w-16 items-center justify-center rounded-2xl border border-surface-border bg-surface-subtle">
          <AlertCircle className="h-8 w-8 text-ink-faint" />
        </div>
        <div>
          <p className="text-base font-semibold text-ink">
            {!canPreview ? 'Preview not available' : 'Original preview unavailable'}
          </p>
          <p className="mt-2 max-w-sm text-sm leading-6 text-ink-muted">
            {!canPreview
              ? 'This file type cannot be previewed inline.'
              : 'Could not load the source file. The parsed extraction is still available on the right.'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {canPreview && previewUrl && (
            <button
              type="button"
              onClick={() => setRetryCount((n) => n + 1)}
              className="inline-flex items-center gap-2 rounded-lg border border-surface-border bg-surface-muted px-3 py-2 text-sm font-medium text-ink-muted transition-colors hover:bg-surface-subtle hover:text-ink"
            >
              <RotateCcw className="h-4 w-4" />
              Retry
            </button>
          )}
          {fileUrl && (
            <a
              href={fileUrl}
              download={doc.filename || 'document'}
              className="inline-flex items-center gap-2 rounded-lg border border-surface-border bg-surface-muted px-3 py-2 text-sm font-medium text-ink-muted transition-colors hover:bg-surface-subtle hover:text-ink"
            >
              <Download className="h-4 w-4" />
              Download original
            </a>
          )}
        </div>
      </div>
    )
  }

  if (state === 'loading') {
    return (
      <div className="flex h-full items-center justify-center text-sm text-ink-muted">
        Loading original preview...
      </div>
    )
  }

  if (isOffice) {
    return (
      <div className="flex h-full flex-col overflow-hidden">
        <div className="flex shrink-0 items-center justify-between border-b border-surface-border bg-surface/80 px-3 py-2">
          <span className="text-xs text-ink-faint">
            {contradictionClauses.length > 0 ? `${contradictionClauses.length} highlighted clause${contradictionClauses.length === 1 ? '' : 's'}` : 'Original preview'}
          </span>
          {zoomControls}
        </div>
        <div className="min-h-0 flex-1 overflow-hidden bg-white">
          <iframe
            srcDoc={highlightedHtmlPreview}
            className="block h-full w-full border-0 bg-white"
            title={doc.filename || 'Document preview'}
            sandbox="allow-same-origin"
          />
        </div>
      </div>
    )
  }

  if (!objectUrl) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-ink-muted">
        Loading original preview...
      </div>
    )
  }

  if (ext === 'pdf') {
    return (
      <div className="flex h-full flex-col overflow-hidden">
        <div className="flex shrink-0 items-center justify-between border-b border-surface-border bg-surface/80 px-3 py-2">
          <span className="truncate text-xs text-ink-faint">
            {firstContradictionText ? 'Searching first contradiction clause in PDF' : 'Original PDF'}
          </span>
          {zoomControls}
        </div>
        {hasPageRange && (
          <div className="shrink-0 border-b border-amber-400/20 bg-amber-400/5 px-4 py-2 text-xs text-amber-300">
            Showing full original document. Extraction was limited to pages {startPage ?? 1}–{endPage ?? '?'}.
          </div>
        )}
        <div className="min-h-0 flex-1">
          <PdfViewer src={objectUrl} zoom={zoom} scrollRef={scrollRef} fileLabel={doc.filename || 'pdf'} />
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="flex shrink-0 items-center justify-between border-b border-surface-border bg-surface/80 px-3 py-2">
        <span className="text-xs text-ink-faint">Original image</span>
        {zoomControls}
      </div>
      <div ref={scrollRef} className="min-h-0 flex-1 overflow-auto bg-surface-subtle/40 p-6">
        <div className="flex min-h-full items-center justify-center">
          <img
            src={objectUrl}
            alt={doc.filename || 'Original document'}
            className="rounded-lg object-contain shadow-card"
            style={{
              width: `${zoom}%`,
              maxWidth: zoom <= 100 ? '100%' : 'none',
              maxHeight: zoom <= 100 ? '100%' : 'none',
            }}
          />
        </div>
      </div>
    </div>
  )
}

function ContentTab({ doc }) {
  const content = doc.content_text || 'No parsed content available.'

  return (
    <div className="px-6 py-5">
      <div className="prose prose-sm dark:prose-invert max-w-none prose-headings:text-ink prose-p:text-ink-muted prose-strong:text-ink prose-a:text-brand prose-code:text-brand dark:prose-code:text-cyan-200 prose-pre:border prose-pre:border-surface-border prose-pre:bg-surface-muted">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {content}
        </ReactMarkdown>
      </div>
    </div>
  )
}

function MetadataTab({ doc }) {
  const fields = [
    { label: 'document_id', value: doc.id },
    { label: 'job_id', value: doc.job_id },
    { label: 'filename', value: doc.filename },
    { label: 'model', value: doc.model_id },
    { label: 'status', value: doc.job_status },
    { label: 'created_at', value: doc.created_at ? new Date(doc.created_at).toLocaleString() : null },
    { label: 'processed_at', value: doc.processed_at || doc.updated_at ? new Date(doc.processed_at || doc.updated_at).toLocaleString() : null },
    { label: 'page_count', value: doc.page_count ?? doc.pages },
    { label: 'start_page', value: doc.meta?.start_page ?? null },
    { label: 'end_page', value: doc.meta?.end_page ?? null },
    { label: 'file_type', value: getExt(doc.filename).toUpperCase() || null },
    { label: 'file_size', value: formatSize(doc.file_size) },
    { label: 'extraction_duration', value: doc.extraction_duration || doc.duration_ms },
  ]

  return (
    <div className="p-5">
      <div className="overflow-hidden rounded-xl border border-surface-border">
        {fields.map(({ label, value }) => (
          <div key={label} className="grid grid-cols-[180px_minmax(0,1fr)] gap-4 border-b border-surface-border px-4 py-3 last:border-b-0">
            <span className="text-xs font-semibold uppercase tracking-wider text-ink-faint">{label}</span>
            <span className="truncate font-mono text-sm text-ink-muted">{value == null || value === '' ? '-' : String(value)}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function RawTab({ doc }) {
  const raw = useMemo(() => JSON.stringify(doc, null, 2), [doc])

  return (
    <pre className="whitespace-pre-wrap break-words p-5 font-mono text-xs leading-6 text-ink-muted">
      {raw}
    </pre>
  )
}

export default function SplitViewer({ doc, documents = [], isOpen, onClose, onSelectDoc, onStartNewExtraction }) {
  const { backendUrl } = useApp()
  const { jobs, updateJob, removeJob } = useJobs()
  const navigate = useNavigate()
  const containerRef = useRef(null)

  const [activeTab, setActiveTab] = useState('content')
  const [fullContentText, setFullContentText] = useState(null)
  const [splitPct, setSplitPct] = useState(50)
  const [leftScrollEl, setLeftScrollEl] = useState(null)
  const [rightScrollEl, setRightScrollEl] = useState(null)
  const [isDraggingDivider, setIsDraggingDivider] = useState(false)
  const [showPreview, setShowPreview] = useState(true)
  const [activePolicyReview, setActivePolicyReview] = useState(doc?.policy_review || null)
  const [isDocumentDrawerOpen, setIsDocumentDrawerOpen] = useState(false)
  const [documentSearch, setDocumentSearch] = useState('')
  const [copiedParsed, setCopiedParsed] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [retrying, setRetrying] = useState(false)
  const [actionError, setActionError] = useState(null)
  const [confirmDelete, setConfirmDelete] = useState(false)

  const job = jobs.find((item) => item.job_id === doc?.job_id)
  const isFailed = job?.status === 'failed'
  const displayName = doc ? getFriendlyName(doc) : 'Document'
  const enrichedDoc = useMemo(
    () =>
      doc
        ? {
            ...doc,
            ...(fullContentText != null ? { content_text: fullContentText } : {}),
            ...(activePolicyReview ? { policy_review: activePolicyReview } : {}),
          }
        : doc,
    [doc, fullContentText, activePolicyReview]
  )
  const rawJson = useMemo(() => JSON.stringify(enrichedDoc || {}, null, 2), [enrichedDoc])
  const currentDocId = doc?.id ?? doc?.job_id ?? null
  const currentDocIndex = useMemo(
    () => documents.findIndex((item) => (item.id ?? item.job_id) === currentDocId),
    [documents, currentDocId]
  )
  const totalDocuments = documents.length || 1
  const deferredDocumentSearch = useDeferredValue(documentSearch)
  const filteredDocuments = useMemo(() => {
    const query = deferredDocumentSearch.trim().toLowerCase()
    if (!query) return documents

    return documents.filter((item) => {
      const friendlyName = getFriendlyName(item).toLowerCase()
      const filename = (item.filename || '').toLowerCase()
      const identifier = String(item.id ?? item.job_id ?? '').toLowerCase()
      return (
        friendlyName.includes(query) ||
        filename.includes(query) ||
        identifier.includes(query)
      )
    })
  }, [documents, deferredDocumentSearch])

  useEffect(() => {
    setConfirmDelete(false)
    setActionError(null)
    setCopiedParsed(false)
    setFullContentText(null)
    setActivePolicyReview(doc?.policy_review || null)
    setIsDocumentDrawerOpen(false)
    setDocumentSearch('')
    setActiveTab('content')
  }, [currentDocId, doc?.policy_review])

  useEffect(() => {
    if (!doc?.job_id || !backendUrl) return
    fetch(`${backendUrl}/v1/jobs/${doc.job_id}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        const document = data?.documents?.[0]
        const text = document?.content_text
        if (text != null) setFullContentText(text)
        if (document?.policy_review) setActivePolicyReview(document.policy_review)
      })
      .catch(() => {})
  }, [doc?.job_id, backendUrl])

  useEffect(() => {
    if (!leftScrollEl || !rightScrollEl) return
    let syncing = false
    const sync = (from, to) => () => {
      if (syncing) return
      syncing = true
      const max = from.scrollHeight - from.clientHeight
      if (max > 0) to.scrollTop = (from.scrollTop / max) * (to.scrollHeight - to.clientHeight)
      requestAnimationFrame(() => { syncing = false })
    }
    const onLeft = sync(leftScrollEl, rightScrollEl)
    const onRight = sync(rightScrollEl, leftScrollEl)
    leftScrollEl.addEventListener('scroll', onLeft, { passive: true })
    rightScrollEl.addEventListener('scroll', onRight, { passive: true })
    return () => {
      leftScrollEl.removeEventListener('scroll', onLeft)
      rightScrollEl.removeEventListener('scroll', onRight)
    }
  }, [leftScrollEl, rightScrollEl])

  const onDividerMouseDown = useCallback((event) => {
    event.preventDefault()
    setIsDraggingDivider(true)
    document.body.classList.add('is-resizing')

    const container = containerRef.current
    if (!container) return

    const onMouseMove = (moveEvent) => {
      const rect = container.getBoundingClientRect()
      const pct = ((moveEvent.clientX - rect.left) / rect.width) * 100
      setSplitPct(Math.min(62, Math.max(38, pct)))
    }
    const onMouseUp = () => {
      setIsDraggingDivider(false)
      document.body.classList.remove('is-resizing')
      document.removeEventListener('mousemove', onMouseMove)
      document.removeEventListener('mouseup', onMouseUp)
    }
    document.addEventListener('mousemove', onMouseMove)
    document.addEventListener('mouseup', onMouseUp)
  }, [])

  const handleDownloadParsed = () => {
    const content = enrichedDoc.content_text || ''
    const blob = new Blob([content], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `${enrichedDoc.filename || 'document'}.txt`
    anchor.click()
    URL.revokeObjectURL(url)
  }

  const handleCopyParsed = async () => {
    await navigator.clipboard.writeText(enrichedDoc.content_text || rawJson)
    setCopiedParsed(true)
    setTimeout(() => setCopiedParsed(false), 1800)
  }

  const handleOpenChat = () => {
    navigate('/chat', { state: { groundingDoc: doc } })
  }

  const handleDelete = async () => {
    if (!confirmDelete) {
      setConfirmDelete(true)
      setTimeout(() => setConfirmDelete(false), 3000)
      return
    }
    setDeleting(true)
    setActionError(null)
    try {
      await deleteJob(doc.job_id, backendUrl)
      removeJob(doc.job_id)
      onClose()
    } catch (error) {
      setActionError(error.message || 'Delete failed')
      setDeleting(false)
      setConfirmDelete(false)
    }
  }

  const handleRetry = async () => {
    setRetrying(true)
    setActionError(null)
    try {
      await retryJob(doc.job_id, backendUrl)
      updateJob(doc.job_id, { status: 'pending', documents: [] })
    } catch (error) {
      setActionError(error.message || 'Retry failed')
    } finally {
      setRetrying(false)
    }
  }

  const handleSelectDoc = useCallback(
    (nextDocId) => {
      const nextDoc = documents.find((item) => String(item.id ?? item.job_id) === nextDocId)
      if (nextDoc && onSelectDoc) {
        onSelectDoc(nextDoc)
        setIsDocumentDrawerOpen(false)
      }
    },
    [documents, onSelectDoc]
  )

  const handlePolicyResultChange = useCallback((review) => {
    setActivePolicyReview(review)
  }, [])

  const handleStepDoc = useCallback(
    (delta) => {
      if (currentDocIndex < 0) return
      const nextDoc = documents[currentDocIndex + delta]
      if (nextDoc && onSelectDoc) onSelectDoc(nextDoc)
    },
    [currentDocIndex, documents, onSelectDoc]
  )

  if (!isOpen || !doc) return null

  return (
    <section className="relative flex h-full min-w-0 flex-col overflow-hidden rounded-2xl border border-surface-border bg-surface/95 shadow-card">
      <header className="flex min-h-14 flex-wrap items-center gap-3 border-b border-surface-border bg-surface-subtle/40 px-4 py-2">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onClose}
            className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-surface-border bg-surface-muted px-2.5 py-1.5 text-xs font-medium text-ink-muted transition-colors hover:bg-surface-subtle hover:text-ink"
          >
            &larr; Documents
          </button>
          <button
            type="button"
            onClick={() => setIsDocumentDrawerOpen(true)}
            className="inline-flex items-center gap-1.5 rounded-lg border border-surface-border bg-surface-muted px-2.5 py-1.5 text-xs font-medium text-ink-muted transition-colors hover:bg-surface-subtle hover:text-ink"
          >
            <Files className="h-3.5 w-3.5" />
            Documents
          </button>
          {onStartNewExtraction && (
            <button
              type="button"
              onClick={onStartNewExtraction}
              title="Close viewer and start a new extraction"
              className="inline-flex items-center gap-1.5 rounded-lg border border-brand/25 bg-brand/10 px-2.5 py-1.5 text-xs font-semibold text-brand transition-colors hover:bg-brand/20"
            >
              <Plus className="h-3.5 w-3.5" />
              New extraction
            </button>
          )}
        </div>

        <div className="flex min-w-0 flex-1 items-center gap-1.5">
          <IconButton
            label="Previous document"
            onClick={() => handleStepDoc(-1)}
            disabled={currentDocIndex <= 0}
          >
            <ChevronLeft className="h-4 w-4" />
          </IconButton>
          <div className="flex min-w-0 flex-1 items-center gap-2 rounded-lg border border-surface-border bg-surface-muted px-3 py-1.5">
            <FileText className="h-4 w-4 shrink-0 text-brand" />
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-ink">{displayName}</p>
              {(doc.id || doc.job_id) && (
                <p className="truncate font-mono text-[10px] text-ink-faint">{doc.id || doc.job_id}</p>
              )}
            </div>
          </div>
          <IconButton
            label="Next document"
            onClick={() => handleStepDoc(1)}
            disabled={currentDocIndex < 0 || currentDocIndex >= totalDocuments - 1}
          >
            <ChevronRight className="h-4 w-4" />
          </IconButton>
          <span className="hidden whitespace-nowrap text-xs text-ink-faint md:inline">
            {currentDocIndex >= 0 ? currentDocIndex + 1 : 1} of {totalDocuments}
          </span>
        </div>

        <div className="ml-auto flex shrink-0 items-center gap-2">
          <Badge variant={doc.job_status} dot>{doc.job_status}</Badge>
          <span className="hidden max-w-36 items-center gap-1 rounded-md border border-surface-border bg-surface-muted px-2 py-1 text-[11px] font-mono text-ink-muted md:inline-flex">
            <Cpu className="h-3 w-3" />
            <span className="truncate">{doc.model_id || 'No model'}</span>
          </span>
        </div>

        <div className="flex shrink-0 items-center gap-1.5">
          <IconButton
            label={showPreview ? 'Hide original pane' : 'Show original pane'}
            onClick={() => setShowPreview((value) => !value)}
          >
            {showPreview ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          </IconButton>
          <IconButton label="Chat with document" onClick={handleOpenChat} active>
            <MessageSquare className="h-4 w-4" />
          </IconButton>
          <IconButton
            label="Policy review"
            onClick={() => setActiveTab('policy')}
            active={activeTab === 'policy'}
          >
            <Search className="h-4 w-4" />
          </IconButton>
          {isFailed && (
            <IconButton label="Retry job" onClick={handleRetry} disabled={retrying}>
              <RotateCcw className={`h-4 w-4 ${retrying ? 'animate-spin' : ''}`} />
            </IconButton>
          )}
          <IconButton
            label={confirmDelete ? 'Confirm delete document' : 'Delete document'}
            onClick={handleDelete}
            disabled={deleting}
            danger
            active={confirmDelete}
          >
            <Trash2 className="h-4 w-4" />
          </IconButton>
          <IconButton label="Close review" onClick={onClose}>
            <X className="h-4 w-4" />
          </IconButton>
        </div>
      </header>

      {actionError && (
        <div className="flex items-center gap-2 border-b border-red-400/20 bg-red-400/5 px-5 py-2 text-sm text-red-400">
          <AlertCircle className="h-4 w-4 shrink-0" />
          {actionError}
        </div>
      )}

      {isDocumentDrawerOpen && (
        <div className="absolute inset-0 z-20 flex">
          <button
            type="button"
            aria-label="Close document drawer"
            onClick={() => setIsDocumentDrawerOpen(false)}
            className="absolute inset-0 bg-black/35"
          />
          <aside className="relative z-10 flex h-full w-full max-w-sm flex-col border-r border-surface-border bg-surface shadow-card">
            <div className="flex items-center justify-between border-b border-surface-border px-4 py-3">
              <div>
                <p className="text-sm font-semibold text-ink">Documents</p>
                <p className="text-xs text-ink-faint">{totalDocuments} available in review mode</p>
              </div>
              <IconButton label="Close document drawer" onClick={() => setIsDocumentDrawerOpen(false)}>
                <X className="h-4 w-4" />
              </IconButton>
            </div>

            <div className="border-b border-surface-border px-4 py-3">
              <div className="flex items-center gap-2 rounded-lg border border-surface-border bg-surface-muted px-3 py-2">
                <Search className="h-4 w-4 shrink-0 text-ink-faint" />
                <input
                  type="text"
                  value={documentSearch}
                  onChange={(event) => setDocumentSearch(event.target.value)}
                  placeholder="Search documents"
                  aria-label="Search review documents"
                  className="w-full bg-transparent text-sm text-ink outline-none placeholder:text-ink-faint"
                />
              </div>
            </div>

            <div className="flex-1 overflow-y-auto p-2">
              {filteredDocuments.length === 0 ? (
                <div className="rounded-xl border border-dashed border-surface-border px-4 py-8 text-center text-sm text-ink-faint">
                  No documents match that search.
                </div>
              ) : (
                filteredDocuments.map((item) => {
                  const itemId = item.id ?? item.job_id
                  const isActive = itemId === currentDocId
                  return (
                    <button
                      key={itemId}
                      type="button"
                      onClick={() => handleSelectDoc(String(itemId))}
                      className={`mb-1 flex w-full items-start gap-3 rounded-xl border px-3 py-3 text-left transition-colors ${
                        isActive
                          ? 'border-brand/25 bg-brand/10 text-ink'
                          : 'border-transparent text-ink-muted hover:border-surface-border hover:bg-surface-subtle hover:text-ink'
                      }`}
                    >
                      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-surface-muted">
                        <FileText className={`h-4 w-4 ${isActive ? 'text-brand' : 'text-ink-faint'}`} />
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center justify-between gap-2">
                          <p className="truncate text-sm font-medium">{getFriendlyName(item)}</p>
                          <Badge variant={item.job_status} dot>{item.job_status}</Badge>
                        </div>
                        <p className="mt-1 truncate text-xs text-ink-faint">{item.filename || 'Untitled file'}</p>
                        <div className="mt-2 flex items-center gap-2 text-[11px] text-ink-faint">
                          <span className="truncate font-mono">{item.model_id || 'No model'}</span>
                          {item.created_at && <span>{new Date(item.created_at).toLocaleDateString()}</span>}
                        </div>
                      </div>
                    </button>
                  )
                })
              )}
            </div>
          </aside>
        </div>
      )}

      <div
        ref={containerRef}
        className="flex-1 min-h-0 overflow-hidden lg:flex"
        style={{ cursor: isDraggingDivider ? 'col-resize' : 'default' }}
      >
        {showPreview && (
          <>
            <section className="flex h-1/2 min-h-[420px] flex-col overflow-hidden border-b border-surface-border lg:h-full lg:min-w-[420px] lg:border-b-0" style={{ width: `${splitPct}%` }}>
              <div className="flex shrink-0 items-center justify-between gap-3 border-b border-surface-border bg-surface-muted/30 px-4 py-2">
                <div className="flex min-w-0 items-center gap-2">
                  <Eye className="h-4 w-4 text-ink-faint" />
                  <span className="text-xs font-semibold uppercase tracking-wider text-ink-faint">Original</span>
                  <span className="hidden truncate text-xs text-ink-faint lg:inline">{doc.filename || displayName}</span>
                </div>
              </div>
              <div className="flex-1 min-h-0 overflow-hidden bg-surface-subtle/20">
                <OriginalPreview
                  doc={doc}
                  backendUrl={backendUrl}
                  policyReview={activePolicyReview}
                  scrollRef={setLeftScrollEl}
                />
              </div>
            </section>
            <div onMouseDown={onDividerMouseDown} className={`split-divider-handle hidden lg:block ${isDraggingDivider ? 'is-dragging' : ''}`} />
          </>
        )}

        <section className="flex min-h-[420px] flex-1 flex-col overflow-hidden lg:min-w-[420px]">
          <div className="flex shrink-0 items-center justify-between gap-3 border-b border-surface-border bg-surface-muted/30 px-4 py-2">
            <div className="flex min-w-0 items-center gap-2">
              <Hash className="h-4 w-4 text-brand" />
              {TABS.map((tab) => (
                <button
                  key={tab.key}
                  type="button"
                  onClick={() => setActiveTab(tab.key)}
                  className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                    activeTab === tab.key
                      ? 'bg-surface border border-surface-border text-ink'
                      : 'text-ink-muted hover:text-ink'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
            <div className="flex shrink-0 items-center gap-1.5">
              <span className="hidden text-xs text-ink-faint md:inline">
                {activeTab === 'content' ? `${(enrichedDoc.content_text || '').length.toLocaleString()} chars` : activeTab === 'raw' ? 'JSON' : 'Details'}
              </span>
              <IconButton label={copiedParsed ? 'Copied results' : 'Copy results'} onClick={handleCopyParsed} active={copiedParsed}>
                {copiedParsed ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
              </IconButton>
              <IconButton label="Download results" onClick={handleDownloadParsed}>
                <Download className="h-4 w-4" />
              </IconButton>
            </div>
          </div>
          <div ref={setRightScrollEl} className="flex-1 overflow-auto">
            {activeTab === 'content' && <ContentTab doc={enrichedDoc} />}
            {activeTab === 'policy' && <PolicyReviewPanel doc={enrichedDoc} onResultChange={handlePolicyResultChange} />}
            {activeTab === 'metadata' && <MetadataTab doc={enrichedDoc} />}
            {activeTab === 'raw' && <RawTab doc={enrichedDoc} />}
          </div>
        </section>
      </div>
    </section>
  )
}
