import { useEffect, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'

export default function Modal({ open, onClose, title, children, wide = false }) {
  const handleKeyDown = useCallback(
    (e) => {
      if (e.key === 'Escape') onClose()
    },
    [onClose]
  )

  useEffect(() => {
    if (open) {
      document.addEventListener('keydown', handleKeyDown)
      document.body.style.overflow = 'hidden'
    }
    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      document.body.style.overflow = ''
    }
  }, [open, handleKeyDown])

  if (!open) return null

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center animate-fade-in">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div
        className={`relative z-10 mx-4 max-h-[85vh] overflow-auto rounded-2xl bg-white shadow-modal ${
          wide ? 'w-full max-w-4xl' : 'w-full max-w-lg'
        }`}
      >
        {title && (
          <div className="flex items-center justify-between border-b border-surface-border px-6 py-4">
            <h2 className="text-lg font-semibold text-ink">{title}</h2>
            <button
              onClick={onClose}
              className="rounded-lg p-1 text-ink-muted transition-colors hover:bg-surface-subtle hover:text-ink"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        )}
        <div className="p-6">{children}</div>
      </div>
    </div>,
    document.body
  )
}
