/** Append a literal schema key without confusing slashes with pointer separators. */
export function appendPointer(path, key) {
  return `${path || ''}/${String(key).replaceAll('~', '~0').replaceAll('/', '~1')}`
}

/** Use the clause editor only when both the schema and saved values are strings. */
export function canEditStringList(definition, value) {
  return definition.type === 'array' && definition.items?.type === 'string'
    && (value == null || (Array.isArray(value) && value.every(item => typeof item === 'string')))
}

/** Apply one deliberate clause edit without trimming, coercing or sorting source text. */
export function editStringList(value, action) {
  const items = value == null ? [] : [...value]
  if (action.type === 'append') return [...items, '']
  if (!Number.isInteger(action.index) || action.index < 0 || action.index >= items.length) throw new Error('Choose an existing clause.')
  if (action.type === 'remove') return items.filter((_, index) => index !== action.index)
  if (action.type !== 'replace' || typeof action.text !== 'string') throw new Error('Enter clause text.')
  items[action.index] = action.text
  return items
}

/** Keep paragraph editing comfortable without imposing a scrolling page-height control. */
export function textRows(value, minimum = 5) {
  return Math.min(16, Math.max(minimum, String(value ?? '').split('\n').reduce((count, line) => count + Math.max(1, Math.ceil(line.length / 85)), 0)))
}
