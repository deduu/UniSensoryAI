import { useState, useMemo } from 'react'
import { Search, FileText, FileSpreadsheet, FileImage, File, CheckSquare, Square, PanelRightClose, PanelRight, Info } from 'lucide-react'
import { useDocuments } from '../../hooks/useDocuments'

const FILE_ICONS = {
  pdf: FileText,
  xlsx: FileSpreadsheet, xls: FileSpreadsheet,
  png: FileImage, jpg: FileImage, jpeg: FileImage, webp: FileImage, gif: FileImage,
}

function getFileIcon(filename) {
  const ext = filename?.split('.').pop()?.toLowerCase() || ''
  return FILE_ICONS[ext] || File
}

export default function DocumentGroundingPanel({ selectedIds, setSelectedIds, collapsed, onToggle }) {
  const { documents } = useDocuments()
  const [search, setSearch] = useState('')

  const filtered = useMemo(() => {
    if (!search.trim()) return documents
    const q = search.toLowerCase()
    return documents.filter((d) => d.filename?.toLowerCase().includes(q))
  }, [documents, search])

  const toggleDoc = (docId) => {
    setSelectedIds((prev) => prev.includes(docId) ? prev.filter((id) => id !== docId) : [...prev, docId])
  }

  const selectAll = () => setSelectedIds(filtered.map((d) => d.id))
  const deselectAll = () => setSelectedIds([])

  const estimatedTokens = useMemo(() => {
    let total = 0
    for (const doc of documents) {
      if (selectedIds.includes(doc.id) && doc.content_text) {
        total += Math.ceil(doc.content_text.length / 4)
      }
    }
    return total
  }, [documents, selectedIds])

  if (collapsed) {
    return (
      <div className="flex flex-col items-center py-3 gap-2 border-l border-surface-border/50 bg-surface/20 backdrop-blur-sm w-12 shrink-0">
        <button onClick={onToggle} className="p-2 rounded-lg text-ink-muted hover:bg-surface-subtle hover:text-ink transition-colors" title="Expand documents panel">
          <PanelRight className="h-4 w-4" />
        </button>
        {selectedIds.length > 0 && (
          <div className="flex items-center justify-center h-6 w-6 rounded-full bg-brand/20 text-[10px] font-bold text-brand-hover">
            {selectedIds.length}
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="flex flex-col w-72 shrink-0 border-l border-surface-border/50 bg-surface/20 backdrop-blur-sm">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-3 border-b border-surface-border/50">
        <div>
          <h3 className="text-xs font-semibold text-ink">Document Context</h3>
          <p className="text-[10px] text-ink-faint mt-0.5">Ground responses in your docs</p>
        </div>
        <button onClick={onToggle} className="p-2 rounded-lg text-ink-muted hover:bg-surface-subtle hover:text-ink transition-colors" title="Collapse panel">
          <PanelRightClose className="h-4 w-4" />
        </button>
      </div>

      {/* Search */}
      <div className="px-3 py-2">
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-ink-faint" />
          <input type="text" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Filter documents..." className="w-full rounded-lg bg-surface-muted/50 border border-surface-border pl-8 pr-3 py-1.5 text-xs text-ink placeholder:text-ink-faint focus:border-brand/30 focus:outline-none focus:ring-1 focus:ring-brand/20 transition-all" />
        </div>
      </div>

      {/* Select All / Deselect */}
      <div className="flex items-center gap-2 px-3 pb-2">
        <button onClick={selectAll} className="text-[10px] text-brand-hover hover:text-brand transition-colors">Select All</button>
        <span className="text-ink-faint text-[10px]">·</span>
        <button onClick={deselectAll} className="text-[10px] text-ink-muted hover:text-ink transition-colors">Deselect All</button>
      </div>

      {/* Document List */}
      <div className="flex-1 overflow-y-auto px-2 pb-2 space-y-0.5">
        {filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <FileText className="h-8 w-8 text-ink-faint mb-2" />
            <p className="text-xs text-ink-faint">{search ? 'No matching documents' : 'No processed documents'}</p>
            <p className="text-[10px] text-ink-faint mt-1">Process documents from the Dashboard</p>
          </div>
        ) : (
          filtered.map((doc) => {
            const Icon = getFileIcon(doc.filename)
            const isSelected = selectedIds.includes(doc.id)
            return (
              <button key={doc.id} onClick={() => toggleDoc(doc.id)} className={`w-full flex items-center gap-2.5 rounded-xl px-3 py-2 text-left transition-all duration-150 ${isSelected ? 'bg-brand/10 border border-brand/20' : 'hover:bg-surface-subtle border border-transparent'}`}>
                <div className={`shrink-0 ${isSelected ? 'text-brand-hover' : 'text-ink-faint'}`}>
                  {isSelected ? <CheckSquare className="h-4 w-4" /> : <Square className="h-4 w-4" />}
                </div>
                <Icon className={`h-4 w-4 shrink-0 ${isSelected ? 'text-brand-hover' : 'text-ink-faint'}`} />
                <span className={`text-xs truncate ${isSelected ? 'text-ink font-medium' : 'text-ink-muted'}`}>{doc.filename}</span>
              </button>
            )
          })
        )}
      </div>

      {/* Info Footer */}
      <div className="border-t border-surface-border/50 px-3 py-3 bg-surface/30">
        <div className="flex items-center gap-1.5 text-[11px] text-ink-faint">
          <Info className="h-3 w-3" />
          <span>{selectedIds.length} selected</span>
          <span className="mx-1">·</span>
          <span>~{estimatedTokens.toLocaleString()} tokens</span>
        </div>
        {estimatedTokens > 100000 && (
          <p className="text-[10px] text-amber-500 mt-1">⚠ Large context — may exceed model limits</p>
        )}
      </div>
    </div>
  )
}
