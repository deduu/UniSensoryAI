const DECIMAL_STRING = /^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$/

/** Select explicit currency conventions without assigning an unknown currency. */
export function moneyConvention(currency) {
  const code = typeof currency === 'string' && /^[A-Z]{3}$/.test(currency.trim().toUpperCase())
    ? currency.trim().toUpperCase() : ''
  const indonesian = !code || code === 'IDR'
  return { code, decimal: indonesian ? ',' : '.', group: indonesian ? '.' : ',' }
}

const visibleValue = value => value == null ? '' : String(value)

/** Group an exact canonical decimal string, retaining every fractional digit. */
export function formatMoneyAmount(value, currency) {
  if (typeof value !== 'string' || !DECIMAL_STRING.test(value)) return visibleValue(value)
  const { decimal, group } = moneyConvention(currency)
  const negative = value.startsWith('-')
  const [integer, fraction] = (negative ? value.slice(1) : value).split('.')
  const grouped = integer.replace(/\B(?=(\d{3})+(?!\d))/g, group)
  return `${negative ? '-' : ''}${grouped}${fraction === undefined ? '' : decimal + fraction}`
}

/** Present a currency only when it was supplied alongside a valid decimal string. */
export function formatMoney(value, currency, { withCurrency = true } = {}) {
  const amount = formatMoneyAmount(value, currency)
  if (typeof value !== 'string' || !DECIMAL_STRING.test(value)) return amount
  const { code } = moneyConvention(currency)
  return withCurrency && code ? `${code} ${amount}` : amount
}

function invalidAmount(currency) {
  return moneyConvention(currency).decimal === ','
    ? 'Enter a complete amount using a comma for decimals and dots in three-digit groups.'
    : 'Enter a complete amount using a dot for decimals and commas in three-digit groups.'
}

/** Parse one explicit locale, rejecting incomplete decimals and invalid grouping. */
export function parseMoneyInput(text, currency) {
  if (typeof text !== 'string') throw new TypeError('Amount must be entered as text.')
  const trimmed = text.trim()
  if (!trimmed) return ''
  const { decimal, group } = moneyConvention(currency)
  const groupPattern = group === '.' ? '\\.' : ','
  const decimalPattern = decimal === '.' ? '\\.' : ','
  const integer = `(?:0|[1-9][0-9]*|[1-9][0-9]{0,2}(?:${groupPattern}[0-9]{3})+)`
  const matched = new RegExp(`^(-?)(${integer})(?:${decimalPattern}([0-9]+))?$`).exec(trimmed)
  if (!matched) throw new Error(invalidAmount(currency))
  const [, sign, whole, fraction] = matched
  return `${sign}${whole.replaceAll(group, '')}${fraction === undefined ? '' : '.' + fraction}`
}

/** Block invalid local text or values the controlling form has not applied. */
export function moneyInputValidity(text, value, currency) {
  try {
    return parseMoneyInput(text, currency) === (value ?? '')
      ? '' : 'Wait for the amount update to apply, or correct the unapplied amount before saving.'
  } catch (error) {
    return error.message
  }
}
