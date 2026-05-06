import { ChevronLeft, ChevronRight } from 'lucide-react'

const PAGE_SIZES = [20, 50, 100]

function getPageNumbers(current, total) {
  const pages = []
  if (total <= 7) {
    for (let i = 1; i <= total; i++) pages.push(i)
    return pages
  }
  pages.push(1)
  if (current > 3) pages.push('...')
  const start = Math.max(2, current - 1)
  const end = Math.min(total - 1, current + 1)
  for (let i = start; i <= end; i++) pages.push(i)
  if (current < total - 2) pages.push('...')
  pages.push(total)
  return pages
}

export default function Pagination({
  page,
  pageSize,
  total,
  onPageChange,
  onPageSizeChange,
}) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize))
  const startItem = (page - 1) * pageSize + 1
  const endItem = Math.min(page * pageSize, total)
  const pageNumbers = getPageNumbers(page, totalPages)

  if (total === 0) return null

  return (
    <div className="flex flex-wrap items-center justify-between gap-4 pt-4">
      {/* Info */}
      <div className="text-sm text-ink-muted">
        Showing{' '}
        <span className="font-medium text-ink">
          {startItem}–{endItem}
        </span>{' '}
        of{' '}
        <span className="font-medium text-ink">{total}</span> documents
      </div>

      {/* Page Buttons */}
      <div className="flex items-center gap-1">
        <button
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
          className="inline-flex items-center justify-center rounded-lg p-1.5 text-ink-muted transition-colors hover:bg-surface-subtle hover:text-ink disabled:opacity-30 disabled:cursor-not-allowed"
        >
          <ChevronLeft className="h-4 w-4" />
        </button>

        {pageNumbers.map((p, idx) =>
          p === '...' ? (
            <span
              key={`e${idx}`}
              className="px-2 text-sm text-ink-faint"
            >
              …
            </span>
          ) : (
            <button
              key={p}
              onClick={() => onPageChange(p)}
              className={`inline-flex h-8 w-8 items-center justify-center rounded-lg text-sm font-medium transition-colors ${
                p === page
                  ? 'bg-brand text-white shadow-sm'
                  : 'text-ink-muted hover:bg-surface-subtle hover:text-ink'
              }`}
            >
              {p}
            </button>
          )
        )}

        <button
          onClick={() => onPageChange(page + 1)}
          disabled={page >= totalPages}
          className="inline-flex items-center justify-center rounded-lg p-1.5 text-ink-muted transition-colors hover:bg-surface-subtle hover:text-ink disabled:opacity-30 disabled:cursor-not-allowed"
        >
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>

      {/* Page Size */}
      <div className="flex items-center gap-2 text-sm text-ink-muted">
        <span>Rows</span>
        <select
          value={pageSize}
          onChange={(e) => onPageSizeChange(Number(e.target.value))}
          className="rounded-lg border border-surface-border bg-surface-muted px-2 py-1 text-sm text-ink focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand/30"
        >
          {PAGE_SIZES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>
    </div>
  )
}
