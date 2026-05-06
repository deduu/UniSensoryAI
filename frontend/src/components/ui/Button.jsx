import { Loader2 } from 'lucide-react'

const VARIANTS = {
  primary:
    'bg-brand text-white hover:bg-brand-hover focus:ring-brand/50',
  secondary:
    'border border-surface-border bg-transparent text-ink hover:bg-surface-subtle focus:ring-brand/50',
  ghost:
    'text-ink-muted hover:bg-surface-subtle focus:ring-brand/50',
  danger:
    'bg-red-600 text-white hover:bg-red-700 focus:ring-red-500/50',
}

export default function Button({
  children,
  variant = 'primary',
  loading = false,
  disabled = false,
  className = '',
  ...props
}) {
  return (
    <button
      className={`inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed ${VARIANTS[variant] || VARIANTS.primary} ${className}`}
      disabled={disabled || loading}
      {...props}
    >
      {loading && <Loader2 className="h-4 w-4 animate-spin" />}
      {children}
    </button>
  )
}
