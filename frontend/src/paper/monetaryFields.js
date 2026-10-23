// Explicit schema semantics: identifiers, fractions and arbitrary extensions are never money.
const MONEY_PATHS = new Set([
  '/fixed_rent', '/minimum_guaranteed_payment', '/subtotal', '/tax_amount',
  '/taxable_amount', '/total', '/vat_amount', '/withholding_amount', '/rounding_adjustment',
  '/installment_schedule/total_gross',
])

/** Identify monetary fields in the canonical PAPER schemas. */
export function isMoneyField(path) {
  return MONEY_PATHS.has(path) || /^\/installment_schedule\/installments\/\d+\/gross_amount$/.test(path || '')
}

/** Resolve the nearest declared currency, preserving an explicitly unknown currency. */
export function fieldCurrency(data, path = '') {
  let current = data
  let currency
  const inspect = () => {
    if (current && typeof current === 'object' && Object.hasOwn(current, 'currency')) currency = current.currency
  }
  inspect()
  for (const token of path.replace(/^\//, '').split('/').filter(Boolean)) {
    current = current?.[token.replaceAll('~1', '/').replaceAll('~0', '~')]
    inspect()
  }
  return currency
}
