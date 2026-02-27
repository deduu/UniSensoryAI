export default function ProgressBar({ value = 0, max = 100, className = '' }) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100))
  return (
    <div className={`h-2 w-full overflow-hidden rounded-full bg-surface-subtle ${className}`}>
      <div
        className="h-full rounded-full bg-brand transition-all duration-500 ease-out"
        style={{ width: `${pct}%` }}
      />
    </div>
  )
}
