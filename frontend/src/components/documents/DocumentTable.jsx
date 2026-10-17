import { useState } from 'react'
import { modelDescription, modelLabel } from '../../jobs/presentation'
import {
  FileText,
  FileSpreadsheet,
  FileImage,
  Presentation,
  File,
  ArrowUp,
  ArrowDown,
  ArrowUpDown,
  Eye,
  MessageSquare,
  Download,
  Trash2,
} from 'lucide-react'
import Badge from '../ui/Badge'

// ─── helpers ─────────────────────────────────────────────────────────────────

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i
const IMAGE_EXTS = new Set(['png', 'jpg', 'jpeg', 'webp', 'gif'])
const SHEET_EXTS = new Set(['xlsx', 'xls', 'csv'])
const SLIDE_EXTS = new Set(['pptx', 'ppt'])

const FILE_ICONS = {
  pdf:  FileText,
  xlsx: FileSpreadsheet, xls: FileSpreadsheet, csv: FileSpreadsheet,
  png:  FileImage, jpg: FileImage, jpeg: FileImage, webp: FileImage, gif: FileImage,
  pptx: Presentation, ppt: Presentation,
}

function getExt(filename) {
  return filename?.split('.').pop()?.toLowerCase() || ''
}

function getFileIcon(filename) {
  return FILE_ICONS[getExt(filename)] || File
}

function getTypeLabel(filename) {
  const ext = getExt(filename)
  if (ext === 'pdf')            return 'PDF'
  if (SHEET_EXTS.has(ext))      return 'Spreadsheet'
  if (SLIDE_EXTS.has(ext))      return 'Presentation'
  if (IMAGE_EXTS.has(ext))      return 'Image'
  if (['docx', 'doc'].includes(ext)) return 'Document'
  return ext.toUpperCase() || '—'
}

function getFriendlyName(doc) {
  const filename = doc.filename || ''
  const bare = filename.replace(/\.[^/.]+$/, '')
  if (!bare || UUID_RE.test(bare)) {
    return IMAGE_EXTS.has(getExt(filename)) ? 'Image extraction' : 'Document'
  }
  return bare
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

function formatSize(bytes) {
  if (!bytes) return '—'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1048576).toFixed(1)} MB`
}

// ─── Sort columns ─────────────────────────────────────────────────────────────

const COLUMNS = [
  { key: 'filename',   label: 'Document', sortable: true },
  { key: 'type',       label: 'Type',     sortable: false },
  { key: 'job_status', label: 'Status',   sortable: true },
  { key: 'model_id',   label: 'Model',    sortable: true },
  { key: 'created_at', label: 'Date',     sortable: true },
  { key: 'file_size',  label: 'Size',     sortable: true },
]

// Which columns to hide when full SplitViewer is open (need space)
const HIDE_WHEN_PANE = new Set(['model_id', 'created_at', 'file_size', 'type'])

// ─── Row actions (hover-revealed) ─────────────────────────────────────────────

function RowActions({ doc, onPreview, onChat, onDownload, onDelete }) {
  return (
    <div className="flex items-center justify-end gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity duration-150">
      {onPreview && <ActionBtn icon={Eye}            label="Preview"           onClick={() => onPreview(doc)}  />}
      {onChat && <ActionBtn icon={MessageSquare}  label="Chat"              onClick={() => onChat(doc)}     className="text-brand/60 hover:text-brand hover:bg-brand/10" />}
      {onDownload && <ActionBtn icon={Download}       label="Download"          onClick={() => onDownload(doc)} />}
      {onDelete && <ActionBtn icon={Trash2}         label="Delete"            onClick={() => onDelete(doc)}   className="hover:text-red-400 hover:bg-red-400/10" />}
    </div>
  )
}

function ActionBtn({ icon: Icon, label, onClick, className = '' }) {
  return (
    <button
      aria-label={label}
      title={label}
      onClick={(e) => { e.stopPropagation(); onClick() }}
      className={`rounded-md p-1.5 text-ink-faint transition-colors hover:bg-surface-subtle hover:text-ink ${className}`}
    >
      <Icon className="h-3.5 w-3.5" />
    </button>
  )
}

// ─── Sort icon ────────────────────────────────────────────────────────────────

function SortIcon({ colKey, sortKey, sortDir }) {
  if (sortKey !== colKey) return <ArrowUpDown className="h-3 w-3 opacity-20" />
  return sortDir === 'asc'
    ? <ArrowUp className="h-3 w-3" />
    : <ArrowDown className="h-3 w-3" />
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function DocumentTable({
  documents,
  activeDocId,
  selectedIds,
  onSelectDoc,
  onToggleSelect,
  onToggleSelectAll,
  onPreview,
  onChat,
  onDownload,
  onDelete,
  isPaneOpen,
}) {
  const [sortKey, setSortKey] = useState(null)
  const [sortDir, setSortDir] = useState('asc')

  const handleSort = (key) => {
    if (sortKey === key) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    else { setSortKey(key); setSortDir('asc') }
  }

  const sorted = [...documents].sort((a, b) => {
    if (!sortKey) return 0
    let va = sortKey === 'model_id' ? modelLabel(a) : a[sortKey] ?? ''
    let vb = sortKey === 'model_id' ? modelLabel(b) : b[sortKey] ?? ''
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
        <table className={`w-full text-left text-sm table-fixed ${isPaneOpen ? 'min-w-[480px]' : 'min-w-[640px] sm:min-w-[736px] md:min-w-[880px] lg:min-w-[960px]'}`}>
          <thead>
            <tr className="border-b border-surface-border bg-surface-muted/60">
              {/* Checkbox */}
              <th className="w-9 px-3 py-2.5">
                <input
                  type="checkbox"
                  checked={allSelected}
                  onChange={onToggleSelectAll}
                  aria-label="Select all"
                  className="h-3.5 w-3.5 rounded border-surface-border bg-surface-muted text-brand focus:ring-brand/30 focus:ring-offset-0"
                />
              </th>

              {COLUMNS.map((col) => {
                if (isPaneOpen && HIDE_WHEN_PANE.has(col.key)) return null

                const widthClass =
                  col.key === 'filename'   ? 'w-auto' :
                  col.key === 'type'       ? 'w-24 hidden sm:table-cell' :
                  col.key === 'job_status' ? 'w-28' :
                  col.key === 'model_id'   ? 'w-36 hidden md:table-cell' :
                  col.key === 'created_at' ? 'w-28' :
                  col.key === 'file_size'  ? 'w-20 hidden lg:table-cell' :
                  ''

                return (
                  <th
                    key={col.key}
                    onClick={col.sortable ? () => handleSort(col.key) : undefined}
                    className={`px-4 py-2.5 text-[10px] font-semibold uppercase tracking-wider text-ink-faint ${
                      col.sortable ? 'cursor-pointer select-none hover:text-ink-muted' : ''
                    } ${widthClass}`}
                  >
                    <span className="inline-flex items-center gap-1">
                      {col.label}
                      {col.sortable && (
                        <SortIcon colKey={col.key} sortKey={sortKey} sortDir={sortDir} />
                      )}
                    </span>
                  </th>
                )
              })}

              {/* Actions column header */}
              <th className="w-28 px-3 py-2.5" aria-label="Actions" />
            </tr>
          </thead>

          <tbody className="divide-y divide-surface-border">
            {sorted.map((doc) => {
              const docId   = doc.id ?? doc.job_id
              const isActive   = docId === activeDocId
              const isSelected = selectedIds.has(docId)
              const Icon       = getFileIcon(doc.filename)
              const friendlyName = getFriendlyName(doc)
              const shortId = (doc.id || doc.job_id || '').slice(0, 16)

              return (
                <tr
                  key={docId}
                  onClick={() => onSelectDoc(doc)}
                  className={`group doc-table-row cursor-pointer ${isActive ? 'is-active' : ''} ${isSelected ? 'is-selected' : ''}`}
                >
                  {/* Checkbox */}
                  <td className="px-3 py-2.5" onClick={(e) => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => onToggleSelect(docId)}
                      aria-label={`Select ${friendlyName}`}
                      className="h-3.5 w-3.5 rounded border-surface-border bg-surface-muted text-brand focus:ring-brand/30 focus:ring-offset-0"
                    />
                  </td>

                  {/* Document name */}
                  <td className="px-4 py-2.5 min-w-0">
                    <div className="flex items-center gap-2.5">
                      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand-light">
                        <Icon className="h-4 w-4 text-brand" />
                      </div>
                      <div className="min-w-0">
                        <p title={doc.filename} className="truncate text-sm font-medium text-ink leading-tight">
                          {friendlyName}
                        </p>
                        {shortId && (
                          <p className="text-[10px] text-ink-faint font-mono truncate leading-tight mt-0.5">
                            {shortId}…
                          </p>
                        )}
                      </div>
                    </div>
                  </td>

                  {/* Type */}
                  {(!isPaneOpen) && (
                    <td className="px-4 py-2.5 text-xs text-ink-faint hidden sm:table-cell">
                      {getTypeLabel(doc.filename)}
                    </td>
                  )}

                  {/* Status */}
                  <td className="px-4 py-2.5">
                    <Badge variant={doc.job_status} dot>
                      {doc.job_status}
                    </Badge>
                  </td>

                  {/* Model */}
                  {(!isPaneOpen) && (
                    <td className="px-4 py-2.5 hidden md:table-cell">
                      <span title={modelDescription(doc)} className="rounded-md bg-surface-muted border border-surface-border px-2 py-0.5 text-[11px] font-mono text-ink-muted truncate max-w-full inline-block">
                        {modelLabel(doc)}
                      </span>
                    </td>
                  )}

                  {/* Date */}
                  {(!isPaneOpen) && (
                    <td className="px-4 py-2.5 text-xs text-ink-faint whitespace-nowrap">
                      {relativeTime(doc.created_at)}
                    </td>
                  )}

                  {/* Size */}
                  {(!isPaneOpen) && (
                    <td className="px-4 py-2.5 text-xs text-ink-faint hidden lg:table-cell">
                      {formatSize(doc.file_size)}
                    </td>
                  )}

                  {/* Actions */}
                  <td className="px-3 py-2.5" onClick={(e) => e.stopPropagation()}>
                    <RowActions
                      doc={doc}
                      onPreview={onPreview}
                      onChat={onChat}
                      onDownload={onDownload}
                      onDelete={onDelete}
                    />
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* No results within current filter */}
      {documents.length === 0 && (
        <div className="py-10 text-center text-sm text-ink-faint border-t border-surface-border">
          No documents match your filters.
        </div>
      )}
    </div>
  )
}
