import { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react'

const ToastContext = createContext(null)

let nextId = 1

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const timers = useRef(new Map())

  const dismiss = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
    const handle = timers.current.get(id)
    if (handle) {
      clearTimeout(handle)
      timers.current.delete(id)
    }
  }, [])

  const push = useCallback(
    (variant, message, opts = {}) => {
      const id = nextId++
      const duration = opts.duration ?? (variant === 'error' ? 7000 : 4500)
      const toast = {
        id,
        variant,
        message,
        title: opts.title || null,
        action: opts.action || null,
      }
      setToasts((prev) => [...prev, toast])
      if (duration > 0) {
        const handle = setTimeout(() => dismiss(id), duration)
        timers.current.set(id, handle)
      }
      return id
    },
    [dismiss]
  )

  const api = useMemo(
    () => ({
      success: (message, opts) => push('success', message, opts),
      error: (message, opts) => push('error', message, opts),
      info: (message, opts) => push('info', message, opts),
      dismiss,
    }),
    [push, dismiss]
  )

  return (
    <ToastContext.Provider value={api}>
      {children}
      <ToastViewport toasts={toasts} onDismiss={dismiss} />
    </ToastContext.Provider>
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within ToastProvider')
  return ctx
}

function ToastViewport({ toasts, onDismiss }) {
  if (toasts.length === 0) return null
  return (
    <div className="pointer-events-none fixed top-4 right-4 z-[60] flex w-[360px] max-w-[calc(100vw-2rem)] flex-col gap-2">
      {toasts.map((t) => (
        <ToastItem key={t.id} toast={t} onDismiss={onDismiss} />
      ))}
    </div>
  )
}

function ToastItem({ toast, onDismiss }) {
  const variantStyles = {
    success: {
      ring: 'border-emerald-400/30',
      glow: 'shadow-[0_0_24px_rgba(16,185,129,0.18)]',
      bar: 'bg-emerald-400',
      icon: 'text-emerald-400',
    },
    error: {
      ring: 'border-red-400/30',
      glow: 'shadow-[0_0_24px_rgba(248,113,113,0.18)]',
      bar: 'bg-red-400',
      icon: 'text-red-400',
    },
    info: {
      ring: 'border-brand/30',
      glow: 'shadow-[0_0_24px_rgba(99,102,241,0.18)]',
      bar: 'bg-brand',
      icon: 'text-brand',
    },
  }[toast.variant] || { ring: 'border-surface-border', glow: '', bar: 'bg-ink-faint', icon: 'text-ink-muted' }

  return (
    <div
      role="status"
      className={`pointer-events-auto relative flex items-start gap-3 overflow-hidden rounded-xl border bg-surface/95 px-4 py-3 backdrop-blur-md animate-slide-in-right ${variantStyles.ring} ${variantStyles.glow}`}
    >
      <span className={`mt-0.5 inline-block h-2 w-2 shrink-0 rounded-full ${variantStyles.bar}`} />
      <div className="min-w-0 flex-1">
        {toast.title && (
          <p className="text-sm font-semibold text-ink leading-snug">{toast.title}</p>
        )}
        <p className={`text-xs leading-snug ${toast.title ? 'text-ink-muted mt-0.5' : 'text-ink'}`}>
          {toast.message}
        </p>
        {toast.action && (
          <button
            onClick={() => {
              toast.action.onClick()
              onDismiss(toast.id)
            }}
            className={`mt-2 inline-flex items-center gap-1 rounded-md border border-surface-border bg-surface-muted px-2.5 py-1 text-xs font-medium ${variantStyles.icon} hover:bg-surface-subtle transition-colors`}
          >
            {toast.action.label}
          </button>
        )}
      </div>
      <button
        onClick={() => onDismiss(toast.id)}
        aria-label="Dismiss"
        className="shrink-0 rounded-md p-1 text-ink-faint transition-colors hover:bg-surface-subtle hover:text-ink"
      >
        <svg viewBox="0 0 16 16" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <path d="M3 3 L13 13 M13 3 L3 13" />
        </svg>
      </button>
    </div>
  )
}
