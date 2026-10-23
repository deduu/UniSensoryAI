import { createElement } from 'react'
import { FormattedDocumentText } from './ReadableText.js'
import { appendPointer } from './readableFields.js'
import { isMoneyField } from '../../paper/monetaryFields.js'
import { formatMoney } from '../../paper/money.js'

function StructuredValue({ value, label = 'View structured value' }) {
  return createElement('details', { className: 'paper-disclosure' },
    createElement('summary', { className: 'text-xs' }, label),
    createElement('pre', { className: 'paper-raw-text mt-2 text-xs' }, JSON.stringify(value, null, 2)),
  )
}

/** Present narrative clauses in source order while preserving exact canonical JSON. */
export default function CanonicalValue({ value, fieldPath, currency, renderSourceLinks, nested = false, formatted = false }) {
  const ownedCurrency = value && typeof value === 'object' && Object.hasOwn(value, 'currency') ? value.currency : currency
  const child = (item, path) => createElement(CanonicalValue, { value: item, fieldPath: path, currency: ownedCurrency, renderSourceLinks, nested: true })
  const source = (path, label) => path && renderSourceLinks ? renderSourceLinks(path, label) : null
  const empty = label => createElement('span', { className: 'italic text-ink-faint' }, label)
  if (value == null) return empty('Unknown')
  if (value === '') return empty('Empty text')
  if (isMoneyField(fieldPath) && typeof value === 'string') return formatMoney(value, currency)
  if (formatted && typeof value === 'string') return createElement('div', { className: 'paper-narrative-value' },
    createElement(FormattedDocumentText, { text: value }),
    createElement(StructuredValue, { value, label: 'Exact text (JSON)' }),
  )
  if (Array.isArray(value) && value.length > 0 && value.every(item => typeof item === 'string')) {
    return createElement('div', { className: 'paper-narrative-value' },
      createElement('ol', { className: 'paper-clause-list' }, value.map((text, index) => {
        const path = fieldPath === undefined ? undefined : appendPointer(fieldPath, index)
        return createElement('li', { key: index, 'data-review-field': path },
          text === '' ? empty('Empty text') : createElement(FormattedDocumentText, { text }),
          source(path, `clause ${index + 1}`),
        )
      })),
      !nested && createElement(StructuredValue, { value, label: 'Exact structured value (JSON)' }),
    )
  }
  if (typeof value === 'object') {
    const entries = Object.entries(value)
    const content = !entries.length ? empty(Array.isArray(value) ? 'No entries' : 'No properties') : Array.isArray(value)
      ? createElement('ol', { className: 'paper-structured-list' }, value.map((item, index) => {
        const path = fieldPath === undefined ? undefined : appendPointer(fieldPath, index)
        return createElement('li', { key: index, 'data-review-field': path },
          createElement('div', { className: 'paper-value-label' }, `Item ${index + 1}`, source(path, `item ${index + 1}`)), child(item, path))
      }))
      : createElement('dl', { className: 'paper-value-properties' }, entries.map(([key, item]) => {
        const path = fieldPath === undefined ? undefined : appendPointer(fieldPath, key)
        const label = key.replaceAll('_', ' ').replace(/^./, letter => letter.toUpperCase())
        return createElement('div', { key, 'data-review-field': path, className: 'paper-value-property' },
          createElement('dt', { className: 'paper-value-label' }, label, source(path, label.toLowerCase())),
          createElement('dd', null, child(item, path)),
        )
      }))
    return createElement('div', { className: 'paper-structured-value' }, content, !nested && createElement(StructuredValue, { value }))
  }
  return String(value)
}
