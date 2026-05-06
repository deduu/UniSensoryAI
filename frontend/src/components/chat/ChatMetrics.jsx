import { Clock, Zap, Coins, Cpu } from 'lucide-react'

export default function ChatMetrics({ metrics }) {
  if (!metrics) return null

  const { latency_ms, prompt_tokens, completion_tokens, total_tokens, model_used } = metrics

  const formatLatency = (ms) => {
    if (!ms) return null
    return ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(1)}s`
  }

  // Rough cost estimation for cloud models
  const estimateCost = () => {
    if (!model_used || !prompt_tokens) return null
    const rates = {
      'gpt-4o': { input: 2.5, output: 10 },
      'gemini-2.0-flash': { input: 0.075, output: 0.3 },
    }
    const rate = rates[model_used]
    if (!rate) return null
    const cost =
      (prompt_tokens / 1_000_000) * rate.input +
      ((completion_tokens || 0) / 1_000_000) * rate.output
    return cost < 0.01 ? `<$0.01` : `$${cost.toFixed(3)}`
  }

  const cost = estimateCost()

  return (
    <div className="flex items-center gap-4 mt-2 pt-2 border-t border-surface-border/50 animate-fade-in">
      {latency_ms && (
        <MetricItem icon={Clock} label={formatLatency(latency_ms)} />
      )}
      {total_tokens && (
        <MetricItem
          icon={Zap}
          label={`${total_tokens.toLocaleString()} tokens`}
          tooltip={`Prompt: ${prompt_tokens?.toLocaleString() || '—'} · Completion: ${completion_tokens?.toLocaleString() || '—'}`}
        />
      )}
      {model_used && (
        <MetricItem icon={Cpu} label={model_used} />
      )}
      {cost && (
        <MetricItem icon={Coins} label={cost} />
      )}
    </div>
  )
}

function MetricItem({ icon: Icon, label, tooltip }) {
  return (
    <div className="flex items-center gap-1.5 text-[11px] text-ink-faint" title={tooltip}>
      <Icon className="h-3 w-3" />
      <span>{label}</span>
    </div>
  )
}
