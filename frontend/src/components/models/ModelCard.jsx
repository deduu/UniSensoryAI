import { Cpu, Cloud } from 'lucide-react'
import Card from '../ui/Card'
import Badge from '../ui/Badge'

export default function ModelCard({ model }) {
  const isCloud = model.type === 'cloud'

  return (
    <Card hover className="flex flex-col p-5">
      <div className="flex items-start justify-between">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-light">
          {isCloud ? (
            <Cloud className="h-5 w-5 text-brand" />
          ) : (
            <Cpu className="h-5 w-5 text-brand" />
          )}
        </div>
        <Badge variant={isCloud ? 'cloud' : 'local'}>{isCloud ? 'Cloud' : 'Local'}</Badge>
      </div>

      <h3 className="mt-3 text-sm font-semibold text-ink">{model.name}</h3>
      <p className="mt-0.5 text-xs text-ink-muted">{model.providerLabel}</p>

      <p className="mt-2 flex-1 text-xs leading-relaxed text-ink-muted">{model.description}</p>

      <div className="mt-3 flex flex-wrap gap-1.5">
        {model.capabilities.map((cap) => (
          <span
            key={cap}
            className="rounded-md bg-surface-subtle px-2 py-0.5 text-xs font-medium text-ink-muted"
          >
            {cap}
          </span>
        ))}
      </div>

      <div className="mt-3 border-t border-surface-border pt-3">
        <div className="flex items-center justify-between text-xs text-ink-muted">
          <span>Parameters</span>
          <span className="font-medium text-ink">{model.params}</span>
        </div>
        <div className="mt-1 flex items-center justify-between text-xs text-ink-muted">
          <span>Model ID</span>
          <code className="font-mono text-ink">{model.id}</code>
        </div>
      </div>
    </Card>
  )
}
