const counter = value => Number.isSafeInteger(value) && value >= 0
const number = value => value.toLocaleString('en-US')

/** Present persisted metering honestly, distinguishing missing data and known subtotals. */
export function usagePresentation(usage) {
  const measured = counter(usage?.measured_call_count) ? usage.measured_call_count : null
  const calls = counter(usage?.call_count) ? usage.call_count : null
  const raw = usage?.estimated_cost
  const amount = typeof raw === 'string' && /^\d+(?:\.\d+)?(?:e[+-]?\d+)?$/i.test(raw) ? Number(raw) : NaN
  const currency = typeof usage?.currency === 'string' && /^[A-Z]{3}$/.test(usage.currency) ? usage.currency : null
  const cost = Number.isFinite(amount) && currency
    ? `${currency} ${amount > 0 && amount < 0.000001 ? '<0.000001' : amount.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 6 })}`
    : 'Unavailable'
  return {
    tokens: counter(usage?.total_tokens) ? number(usage.total_tokens) : 'Unavailable',
    tokenLabel: usage?.coverage === 'complete' ? 'Total reported tokens' : usage?.coverage === 'partial' ? 'Known token subtotal' : 'Reported tokens',
    cost,
    costLabel: usage?.cost_coverage === 'partial' ? 'Known cost estimate' : 'Estimated cost',
    coverage: measured != null && calls != null ? `${number(measured)} of ${number(calls)} calls metered` : 'Usage was not recorded for this attempt.',
  }
}
