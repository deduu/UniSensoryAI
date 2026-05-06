import { useState } from 'react'
import {
  FileText,
  FileSpreadsheet,
  FileImage,
  Presentation,
  File,
  ArrowUp,
  ArrowDown,
  ArrowUpDown,
} from 'lucide-react'
import Badge from '../ui/Badge'

const FILE_ICONS = {
  pdf: FileText,
  xlsx: FileSpreadsheet,
  xls: FileSpreadsheet,
  csv: FileSpreadsheet,
  png: FileImage,
  jpg: FileImage,
  jpeg: FileImage,
  webp: FileImage,
  gif: FileImage,
  pptx: Presentation,
  ppt: Presentation,
}

function getFileIcon(filename) {
  const ext = filename?.split('.').pop()?.toLowerCase() || ''
  return FILE_ICONS[ext] || File
}

function relativeTime(dateStr) {
  if (!dateStr) return '—'
  const now = Date.now()
  const d = new Date(dateStr).getTime()
  const diff = now - d
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days < 7) return `${days}d ago`
  return new Date(dateStr).toLocaleDateString()
}

function formatSize(bytes) {
  if (!bytes) return '—'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1048576).toFixed(1)} MB`
}

const COLUMNS = [
  { key: 'filename', label: 'Name', sortable: true },
  { key: 'job_status', label: 'Status', sortable: true },
  { key: 'model_id', label: 'Model', sortable: true },
  { key: 'created_at', label: 'Date', sortable: true },
  { key: 'file_size', label: 'Size', sortable: true },
]

export default function DocumentTable({
  documents,
  activeDocId,
  selectedIds,
  onSelectDoc,
  onToggleSelect,
  onToggleSelectAll,
  isPaneOpen,
}) {
  const [sortKey, setSortKey] = useState(null)
  const [sortDir, setSortDir] = useState('asc')

  const handleSort = (key) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setSortDir('asc')
    }
  }

  const sorted = [...documents].sort((a, b) => {
    if (!sortKey) return 0
    let va = a[sortKey] ?? ''
    let vb = b[sortKey] ?? ''
    if (typeof va === 'string') va = va.toLowerCase()
    if (typeof vb === 'string') vb = vb.toLowerCase()
    if (va < vb) return sortDir === 'asc' ? -1 : 1
    if (va > vb) return sortDir === 'asc' ? 1 : -1
    return 0
  })

  const allSelected =
    documents.length > 0 && documents.every((d) => selectedIds.has(d.id ?? d.job_id))

  return (
    <div className="overflow-hidden rounded-xl border border-surface-border flex flex-col h-full">
      <div className="flex-1 overflow-auto">
        <table className="w-full text-left text-sm table-fixed min-w-[500px]">
          <thead>
          <tr className="border-b border-surface-border bg-surface-muted/60">
            <th className="w-10 px-3 py-3">
              <input
                type="checkbox"
                checked={allSelected}
                onChange={onToggleSelectAll}
                className="h-3.5 w-3.5 rounded border-surface-border bg-surface-muted text-brand focus:ring-brand/30 focus:ring-offset-0"
              />
            </th>
            {COLUMNS.map((col) => {
              const hideWhenPaneOpen = ['model_id', 'created_at', 'file_size'].includes(col.key);
              if (isPaneOpen && hideWhenPaneOpen) return null;
              
              // Set column widths
              let colWidth = '';
              if (col.key === 'filename') colWidth = 'w-auto';
              else if (col.key === 'job_status') colWidth = 'w-28';
              else if (col.key === 'model_id') colWidth = 'w-32 hidden md:table-cell';
              else if (col.key === 'created_at') colWidth = 'w-32';
              else if (col.key === 'file_size') colWidth = 'w-24 hidden lg:table-cell';

              return (
              <th
                key={col.key}
                onClick={col.sortable ? () => handleSort(col.key) : undefined}
                className={`px-4 py-3 text-xs font-semibold uppercase tracking-wider text-ink-muted ${
                  col.sortable ? 'cursor-pointer select-none hover:text-ink' : ''
                } ${colWidth}`}
              >
                <span className="inline-flex items-center gap-1">
                  {col.label}
                  {col.sortable &&
                    (sortKey === col.key ? (
                      sortDir === 'asc' ? (
                        <ArrowUp className="h-3 w-3" />
                      ) : (
                        <ArrowDown className="h-3 w-3" />
                      )
                    ) : (
                      <ArrowUpDown className="h-3 w-3 opacity-30" />
                    ))}
                </span>
              </th>
            )})}
          </tr>
        </thead>
        <tbody className="divide-y divide-surface-border">
          {sorted.map((doc) => {
            const docId = doc.id ?? doc.job_id
            const isActive = docId === activeDocId
            const isSelected = selectedIds.has(docId)
            const Icon = getFileIcon(doc.filename)

            return (
              <tr
                key={docId}
                onClick={() => onSelectDoc(doc)}
                className={`doc-table-row cursor-pointer ${isActive ? 'is-active' : ''} ${
                  isSelected ? 'is-selected' : ''
                }`}
              >
                <td className="px-3 py-2.5" onClick={(e) => e.stopPropagation()}>
                  <input
                    type="checkbox"
                    checked={isSelected}
                    onChange={() => onToggleSelect(docId)}
                    className="h-3.5 w-3.5 rounded border-surface-border bg-surface-muted text-brand focus:ring-brand/30 focus:ring-offset-0"
                  />
                </td>
                <td className="px-4 py-2.5 min-w-0">
                  <div className="flex items-center gap-2.5">
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand-light">
                      <Icon className="h-4 w-4 text-brand" />
                    </div>
                    <span className="truncate font-medium text-ink block w-full">
                      {doc.filename || 'Untitled'}
                    </span>
                  </div>
                </td>
                <td className="px-4 py-2.5 w-28">
                  <Badge variant={doc.job_status} dot>
                    {doc.job_status}
                  </Badge>
                </td>
                {(!isPaneOpen) && (
                  <td className="px-4 py-2.5 text-ink-muted w-32 hidden md:table-cell">
                    <span className="rounded bg-surface-subtle px-2 py-0.5 text-xs font-mono truncate max-w-full block">
                      {doc.model_id || '—'}
                    </span>
                  </td>
                )}
                {(!isPaneOpen) && (
                  <td className="px-4 py-2.5 text-xs text-ink-muted w-32 truncate">
                    {relativeTime(doc.created_at)}
                  </td>
                )}
                {(!isPaneOpen) && (
                  <td className="px-4 py-2.5 text-xs text-ink-muted w-24 hidden lg:table-cell">
                    {formatSize(doc.file_size)}
                  </td>
                )}
              </tr>
            )
          })}
        </tbody>
      </table>
      </div>
      {documents.length === 0 && (
        <div className="py-12 text-center text-sm text-ink-muted border-t border-surface-border">
          No documents match your filters
        </div>
      )}
    </div>
  )
}
