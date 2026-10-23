import { createElement, useId, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

// Source documents are untrusted. Formatting must never activate their HTML,
// remote assets or links; the raw presentation retains every source character.
const ELEMENTS = [
  'p', 'br', 'strong', 'em', 'del', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
  'ul', 'ol', 'li', 'blockquote', 'hr', 'pre', 'code',
  'table', 'thead', 'tbody', 'tr', 'th', 'td',
]

function ScrollableTable({ children }) {
  return createElement('div', { className: 'paper-readable-table', tabIndex: 0, role: 'region', 'aria-label': 'Recovered table' }, createElement('table', null, children))
}

/** Render document formatting without changing stored text or enabling its URLs. */
export function FormattedDocumentText({ text }) {
  return createElement('div', { className: 'paper-readable-text' }, createElement(ReactMarkdown, {
    remarkPlugins: [remarkGfm],
    skipHtml: true,
    allowedElements: ELEMENTS,
    unwrapDisallowed: true,
    components: { table: ScrollableTable },
  }, typeof text === 'string' ? text : ''))
}

/** Expose unchanged transcription characters as escaped, selectable source text. */
export function RawDocumentText({ text }) {
  return createElement('pre', { className: 'paper-raw-text', 'aria-label': 'Exact recovered text' }, typeof text === 'string' ? text : '')
}

/** Switch the presentation of one immutable transcription between readable and raw. */
export default function ReadableText({ text, label = 'Recovered text' }) {
  const [raw, setRaw] = useState(false)
  const contentId = useId()
  return createElement('div', { className: 'paper-text-reader' },
    createElement('div', { className: 'paper-text-reader-controls', role: 'group', 'aria-label': `${label} presentation` },
      createElement('button', { type: 'button', 'aria-pressed': !raw, 'aria-controls': contentId, className: !raw ? 'paper-primary' : 'paper-secondary', onClick: () => setRaw(false) }, 'Readable'),
      createElement('button', { type: 'button', 'aria-pressed': raw, 'aria-controls': contentId, className: raw ? 'paper-primary' : 'paper-secondary', onClick: () => setRaw(true) }, 'Raw text'),
    ),
    createElement('div', { id: contentId, className: 'paper-text-reader-content' }, createElement(raw ? RawDocumentText : FormattedDocumentText, { text })),
    createElement('p', { className: 'paper-text-reader-note' }, 'Formatting is for reading. Raw text preserves the stored transcription; verify wording against the original PDF.'),
  )
}
