const VARIANTS = {
  pending:    'bg-zinc-500/10 text-zinc-400 border border-zinc-500/20',
  queued:     'bg-sky-400/10 text-sky-300 border border-sky-400/20',
  processing: 'bg-amber-400/10 text-amber-300 border border-amber-400/20',
  completed:  'bg-emerald-400/10 text-emerald-300 border border-emerald-400/20',
  failed:     'bg-red-400/10 text-red-300 border border-red-400/20',
  local:      'bg-indigo-400/10 text-indigo-300 border border-indigo-400/20',
  cloud:      'bg-sky-400/10 text-sky-300 border border-sky-400/20',
}

const DOT_COLORS = {
  processing: 'bg-amber-400',
  completed:  'bg-emerald-400',
  failed:     'bg-red-400',
  queued:     'bg-sky-400',
}

export default function Badge({ children, variant = 'pending', dot = false, className = '' }) {
  const colors = VARIANTS[variant] || VARIANTS.pending

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium ${colors} ${className}`}
    >
      {dot && (
        <span className="relative flex h-1.5 w-1.5 shrink-0">
          {variant === 'processing' && (
            <span className="absolute inline-flex h-full w-full animate-pulse-ring rounded-full bg-amber-400 opacity-75" />
          )}
          <span className={`relative inline-flex h-1.5 w-1.5 rounded-full ${DOT_COLORS[variant] || 'bg-zinc-400'}`} />
        </span>
      )}
      {children}
    </span>
  )
}
