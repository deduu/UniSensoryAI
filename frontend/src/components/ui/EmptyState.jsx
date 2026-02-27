import Button from './Button'

export default function EmptyState({ icon: Icon, heading, subtext, actionLabel, onAction }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      {Icon && (
        <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-surface-subtle">
          <Icon className="h-8 w-8 text-ink-faint" />
        </div>
      )}
      <h3 className="text-lg font-semibold text-ink">{heading}</h3>
      {subtext && <p className="mt-1 max-w-sm text-sm text-ink-muted">{subtext}</p>}
      {actionLabel && onAction && (
        <Button className="mt-4" onClick={onAction}>
          {actionLabel}
        </Button>
      )}
    </div>
  )
}
