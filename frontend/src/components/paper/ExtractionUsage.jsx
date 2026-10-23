import { usagePresentation } from '../../paper/extractionUsage'

const tokens = value => Number.isSafeInteger(value) && value >= 0 ? value.toLocaleString('en-US') : 'Unavailable'

/** Recorded request metering is separate from legal review and provider billing. */
export default function ExtractionUsage({ usage, documentReuse }) {
  const view = usagePresentation(usage)
  const calls = usage?.calls || []
  const prices = [...new Map(calls.filter(call => call.pricing).map(call => [JSON.stringify(call.pricing), call.pricing])).values()]
  return <section className="min-w-0 rounded-lg border border-surface-border bg-surface p-3" aria-label="Extraction tokens and cost">
    <div className="flex flex-wrap items-start justify-between gap-3"><dl className="flex min-w-0 flex-wrap gap-x-8 gap-y-3"><div><dt className="text-xs text-ink-muted">{view.tokenLabel}</dt><dd className="mt-1 text-sm font-semibold">{view.tokens}</dd></div><div><dt className="text-xs text-ink-muted">{view.costLabel}</dt><dd className="mt-1 text-sm font-semibold">{view.cost}</dd></div></dl><p className="text-xs text-ink-muted">{view.coverage}</p></div>
    {documentReuse && <p className="mt-2 text-xs text-ink-muted">Verified OCR was reused for this exact original PDF. These figures cover new model calls; earlier OCR tokens and cost are unavailable and excluded.</p>}
    {usage && <details className="paper-disclosure mt-3 min-w-0"><summary className="text-xs font-medium">Usage breakdown and pricing basis</summary><p className="mt-3 text-xs text-ink-muted">This attempt includes model calls for extraction, review, evidence repair and retries. Provider-reported tokens and configured prices produce an estimate; your actual provider bill may differ. Earlier attempts are excluded. Missing usage or prices remain unavailable.</p>
      <dl className="mt-3 flex flex-wrap gap-x-6 gap-y-2 text-xs"><div><dt className="text-ink-muted">Input tokens</dt><dd>{tokens(usage.input_tokens)}</dd></div><div><dt className="text-ink-muted">Output tokens</dt><dd>{tokens(usage.output_tokens)}</dd></div><div><dt className="text-ink-muted">Token coverage</dt><dd>{usage.coverage}</dd></div><div><dt className="text-ink-muted">Cost coverage</dt><dd>{usage.cost_coverage}</dd></div></dl>
      {prices.map((price, index) => <p key={index} className="mt-3 break-words text-xs text-ink-muted">{price.pricing_id} · {price.model_id} · {price.currency} per million tokens: input {price.input_per_million}, output {price.output_per_million}{price.cached_input_per_million != null ? `, cached input ${price.cached_input_per_million}` : ''}. {price.allowed_response_model_ids?.length > 0 ? `Accepted response models: ${price.allowed_response_model_ids.join(', ')}. ` : ''}{price.as_of ? `Reference date ${price.as_of}. ` : ''}<span className="break-all">{price.source}</span></p>)}
      {!!calls.length && <ol className="mt-3 max-h-72 space-y-2 overflow-auto text-xs" aria-label="Metered model calls">{calls.map(call => <li key={call.sequence} className="min-w-0 rounded bg-surface-muted p-2"><p className="break-words font-medium">{call.sequence}. {call.profile} · {call.purpose} · {call.status}</p><p className="mt-1 break-words text-ink-muted">{call.provider} / {call.model_id}{call.response_model_id && call.response_model_id !== call.model_id ? ` (reported ${call.response_model_id})` : ''} · input {tokens(call.input_tokens)} · output {tokens(call.output_tokens)} · total {tokens(call.total_tokens)} · {usagePresentation(call).cost}{call.error_code ? ` · ${call.error_code}` : ''}</p></li>)}</ol>}
    </details>}
  </section>
}
