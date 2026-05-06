import { useEffect, useState, useMemo, useCallback } from 'react'
import { FileText, Search } from 'lucide-react'
import DocumentTable from '../components/documents/DocumentTable'
import InspectorPane from '../components/documents/InspectorPane'
import Pagination from '../components/documents/Pagination'
import BulkActionsBar from '../components/documents/BulkActionsBar'
import EmptyState from '../components/ui/EmptyState'
import { useDocuments } from '../hooks/useDocuments'
import { useResizablePane } from '../hooks/useResizablePane'

const TYPE_TABS = [
  { key: 'all', label: 'All' },
  { key: 'pdf', label: 'PDF' },
  { key: 'image', label: 'Images' },
  { key: 'office', label: 'Office' },
]





export default function Documents() {
  const { documents, search, setSearch, typeFilter, setTypeFilter } = useDocuments()



  // Pagination
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)

  // Selection
  const [selectedIds, setSelectedIds] = useState(new Set())
  const [activeDoc, setActiveDoc] = useState(null)

  // Inspector pane
  const pane = useResizablePane()

  useEffect(() => {
    document.title = 'Documents — UniSensoryAI'
  }, [])



  // Reset page when filters change
  useEffect(() => {
    setPage(1)
  }, [search, typeFilter, pageSize])

  // Paginated documents
  const paginatedDocs = useMemo(() => {
    const start = (page - 1) * pageSize
    return documents.slice(start, start + pageSize)
  }, [documents, page, pageSize])

  // Handlers
  const handleSelectDoc = useCallback(
    (doc) => {
      setActiveDoc(doc)
      pane.open()
    },
    [pane]
  )

  const handleToggleSelect = useCallback((docId) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(docId)) {
        next.delete(docId)
      } else {
        next.add(docId)
      }
      return next
    })
  }, [])

  const handleToggleSelectAll = useCallback(() => {
    const allIds = paginatedDocs.map((d) => d.id ?? d.job_id)
    const allSelected = allIds.every((id) => selectedIds.has(id))
    if (allSelected) {
      setSelectedIds((prev) => {
        const next = new Set(prev)
        allIds.forEach((id) => next.delete(id))
        return next
      })
    } else {
      setSelectedIds((prev) => {
        const next = new Set(prev)
        allIds.forEach((id) => next.add(id))
        return next
      })
    }
  }, [paginatedDocs, selectedIds])

  const handleBulkDownload = useCallback(() => {
    documents
      .filter((d) => selectedIds.has(d.id ?? d.job_id))
      .forEach((doc) => {
        const content = doc.content_text || ''
        const blob = new Blob([content], { type: 'text/plain' })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `${doc.filename || 'document'}.txt`
        a.click()
        URL.revokeObjectURL(url)
      })
  }, [documents, selectedIds])

  const handleDeselectAll = useCallback(() => {
    setSelectedIds(new Set())
  }, [])

  const handleClosePane = useCallback(() => {
    pane.close()
    setActiveDoc(null)
  }, [pane])

  const isRight = pane.dockPosition === 'right'
  const activeDocId = activeDoc?.id ?? activeDoc?.job_id ?? null

  return (
    <div className="flex flex-col h-[calc(100vh-5rem)]">
      {/* Header & Toolbar */}
      <div className="shrink-0 mb-5 flex flex-col xl:flex-row xl:items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-ink">Documents</h1>
          <p className="mt-1 text-sm text-ink-muted">
            Browse and inspect all extracted documents
          </p>
        </div>
        
        {/* Toolbar Controls */}
        <div className="flex flex-col sm:flex-row items-center gap-3 w-full xl:w-auto">
          {/* Search */}
          <div className="relative w-full sm:w-64 shrink-0">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-faint" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search documents..."
              className="w-full rounded-lg border border-surface-border bg-surface-muted py-2 pl-10 pr-4 text-sm text-ink placeholder:text-ink-faint focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/20"
            />
          </div>

          <div className="flex items-center gap-3 shrink-0">
            {/* Type Filters */}
            <div className="flex rounded-lg bg-surface-muted/50 p-0.5">
              {TYPE_TABS.map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => setTypeFilter(tab.key)}
                  className={`rounded-md px-3 py-1.5 text-xs font-medium transition-all ${
                    typeFilter === tab.key
                      ? 'bg-brand text-white shadow-sm'
                      : 'text-ink-muted hover:text-ink hover:bg-surface-subtle'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      {documents.length === 0 ? (
        <EmptyState
          icon={FileText}
          heading="No documents found"
          subtext="Documents will appear here after processing completes"
        />
      ) : (
        <div
          className={`flex-1 flex min-h-0 ${
            isRight ? 'flex-row' : 'flex-col'
          }`}
        >
          {/* Master Panel - Document List/Table */}
          <div className="flex-1 flex flex-col min-w-0 min-h-0 overflow-hidden">
            <div className="flex-1 overflow-auto">
              <DocumentTable
                documents={paginatedDocs}
                activeDocId={activeDocId}
                selectedIds={selectedIds}
                onSelectDoc={handleSelectDoc}
                onToggleSelect={handleToggleSelect}
                onToggleSelectAll={handleToggleSelectAll}
                isPaneOpen={pane.isOpen && !pane.isMinimized}
              />
            </div>

            {/* Pagination */}
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
          </div>

          {/* Inspector Pane */}
          <InspectorPane
            doc={activeDoc}
            isOpen={pane.isOpen}
            isMinimized={pane.isMinimized}
            isMaximized={pane.isMaximized}
            dockPosition={pane.dockPosition}
            paneWidth={pane.paneWidth}
            onClose={handleClosePane}
            onMinimize={pane.minimize}
            onMaximize={pane.maximize}
            onRestore={pane.restore}
            onDragStart={pane.onDragStart}
            isDragging={pane.isDragging}
          />
        </div>
      )}

      {/* Bulk Actions */}
      <BulkActionsBar
        count={selectedIds.size}
        onDownload={handleBulkDownload}
        onDeselect={handleDeselectAll}
      />
    </div>
  )
}
