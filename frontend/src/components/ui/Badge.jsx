const VARIANTS = {
  pending: 'bg-gray-100 text-gray-600',
  queued: 'bg-gray-100 text-gray-600',
  processing: 'bg-amber-50 text-amber-700',
  completed: 'bg-emerald-50 text-emerald-700',
  failed: 'bg-red-50 text-red-700',
  local: 'bg-indigo-50 text-indigo-700',
  cloud: 'bg-sky-50 text-sky-700',
}

export default function Badge({ children, variant = 'pending', dot = false, className = '' }) {
  const colors = VARIANTS[variant] || VARIANTS.pending

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${colors} ${className}`}
    >
      {dot && (
        <span className="relative flex h-2 w-2">
          {variant === 'processing' && (
            <span className="absolute inline-flex h-full w-full animate-pulse-ring rounded-full bg-amber-400 opacity-75" />
          )}
          <span
            className={`relative inline-flex h-2 w-2 rounded-full ${
              variant === 'processing'
                ? 'bg-amber-500'
                : variant === 'completed'
                  ? 'bg-emerald-500'
                  : variant === 'failed'
                    ? 'bg-red-500'
                    : 'bg-gray-400'
            }`}
          />
        </span>
      )}
      {children}
    </span>
  )
}
