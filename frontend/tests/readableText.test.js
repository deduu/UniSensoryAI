import test from 'node:test'
import assert from 'node:assert/strict'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import ReadableText, { FormattedDocumentText, RawDocumentText } from '../src/components/paper/ReadableText.js'
import CanonicalValue from '../src/components/paper/CanonicalValue.js'

const render = (Component, props) => renderToStaticMarkup(createElement(Component, props))

test('recovered Markdown renders headings, emphasis, paragraphs and clause lists', () => {
  const text = '# Agreement\n\n**Landlord:** Example Owner\n\n1. First clause\n2. Second *clause*'
  const before = text
  const html = render(FormattedDocumentText, { text })
  assert.match(html, /<h1>Agreement<\/h1>/)
  assert.match(html, /<strong>Landlord:<\/strong>/)
  assert.match(html, /<ol>/)
  assert.match(html, /<em>clause<\/em>/)
  assert.equal(text, before)
})

test('recovered tables have semantic rows and remain inside a bounded scrolling container', () => {
  const html = render(FormattedDocumentText, { text: '| Term | Amount |\n| --- | --- |\n| Rent | 125000 |' })
  assert.match(html, /class="paper-readable-table"/)
  assert.match(html, /<table>/)
  assert.match(html, /<th>Term<\/th>/)
  assert.match(html, /<td>125000<\/td>/)
})

test('document content cannot render HTML, active links, remote images or executable URLs', () => {
  const text = '<script>alert(1)</script>\n\n<img src="https://remote.invalid/leak" onerror="alert(1)">\n\n[Visible reference](https://remote.invalid/path)\n\n[Unsafe reference](javascript:alert%281%29)\n\n![remote image](https://remote.invalid/image.png)'
  const html = render(FormattedDocumentText, { text })
  assert.doesNotMatch(html, /<(?:script|img|iframe|a|input)\b/i)
  assert.doesNotMatch(html, /\b(?:href|src|onerror)=/i)
  assert.match(html, /Visible reference/)
  assert.match(html, /Unsafe reference/)
})

test('raw presentation retains exact whitespace, Markdown and HTML as escaped source text', () => {
  const text = '\n  **Raw**\r\n<em>not HTML</em>\nA  B\tC\n'
  const html = render(RawDocumentText, { text })
  const escaped = text.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
  assert.ok(html.includes(escaped))
  assert.match(html, /<pre\b/)
  assert.doesNotMatch(html, /<em>/)
  assert.equal(text, '\n  **Raw**\r\n<em>not HTML</em>\nA  B\tC\n')
})

test('readable and raw controls expose the selected presentation without replacing source', () => {
  const html = render(ReadableText, { text: '**Recovered**', label: 'Recovered page text' })
  assert.match(html, /aria-label="Recovered page text presentation"/)
  assert.match(html, /aria-pressed="true"[^>]*>Readable<\/button>/)
  assert.match(html, /aria-pressed="false"[^>]*>Raw text<\/button>/)
  assert.match(html, /<strong>Recovered<\/strong>/)
})

test('narrative clause arrays are readable in order and retain exact JSON for inspection', () => {
  const value = ['**First clause:** landlord payment.', 'Second clause\nwith original line break.']
  const before = structuredClone(value)
  const html = render(CanonicalValue, { value })
  assert.match(html, /<ol[^>]*class="paper-clause-list"/)
  assert.match(html, /<li><div class="paper-readable-text">/)
  assert.match(html, /<strong>First clause:<\/strong>/)
  assert.match(html, /Exact structured value \(JSON\)/)
  assert.ok(html.indexOf('First clause:') < html.indexOf('Second clause'))
  const escaped = JSON.stringify(value, null, 2).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;')
  assert.ok(html.includes(escaped))
  assert.deepEqual(value, before)
})

test('canonical scalar strings remain literal and mixed objects retain structured JSON', () => {
  assert.equal(render(CanonicalValue, { value: '**Legal name**' }), '**Legal name**')
  assert.match(render(CanonicalValue, { value: null }), /Unknown/)
  assert.equal(render(CanonicalValue, { value: 0 }), '0')
  const mixed = [{ key: '**Exact object**' }, null]
  const before = structuredClone(mixed)
  const html = render(CanonicalValue, { value: mixed })
  assert.match(html, /View structured value/)
  assert.doesNotMatch(html, /paper-clause-list/)
  assert.deepEqual(mixed, before)
})

test('formatting a narrative clause array never enables document-controlled links or images', () => {
  const html = render(CanonicalValue, { value: ['[Citation](https://remote.invalid/track)', '![Image](https://remote.invalid/image)'] })
  assert.doesNotMatch(html, /<(?:a|img)\b/)
  assert.match(html, /Exact structured value \(JSON\)/)
})

test('structured values expose labelled readable leaves and exact nested source pointers', () => {
  const value = { 'payment/details': [{ 'amount~net': '001200.00', active: false, withheld: 0 }], missing: null }
  const before = structuredClone(value)
  const html = render(CanonicalValue, {
    value, fieldPath: '/extensions',
    renderSourceLinks: (fieldPath, label) => createElement('button', { 'data-source-path': fieldPath }, label),
  })
  assert.match(html, /<dl\b/)
  assert.match(html, /Payment\/details/)
  assert.match(html, /Amount~net/)
  assert.match(html, /001200\.00/)
  assert.match(html, /data-source-path="\/extensions\/payment~1details\/0\/amount~0net"/)
  assert.match(html, /data-source-path="\/extensions\/payment~1details\/0\/active"/)
  assert.match(html, /false/)
  assert.match(html, />0</)
  assert.match(html, /View structured value/)
  assert.deepEqual(value, before)
})

test('empty and unknown canonical values remain visibly distinct', () => {
  assert.match(render(CanonicalValue, { value: null }), /Unknown/)
  assert.match(render(CanonicalValue, { value: '' }), /Empty text/)
  assert.match(render(CanonicalValue, { value: [] }), /No entries/)
  assert.match(render(CanonicalValue, { value: {} }), /No properties/)
})

test('narrative items expose their own evidence pointers in source order', () => {
  const paths = []
  const html = render(CanonicalValue, {
    value: ['First', 'Second'], fieldPath: '/other_key_terms',
    renderSourceLinks: path => { paths.push(path); return null },
  })
  assert.deepEqual(paths, ['/other_key_terms/0', '/other_key_terms/1'])
  assert.match(html, /data-review-field="\/other_key_terms\/1"/)
})

test('long scalar text can be formatted without losing its exact stored text', () => {
  const value = '  **Payment:** first\n\nSecond  paragraph.\n'
  const html = render(CanonicalValue, { value, formatted: true })
  assert.match(html, /<strong>Payment:<\/strong>/)
  assert.match(html, /Exact text \(JSON\)/)
  assert.ok(html.includes(JSON.stringify(value, null, 2).replaceAll('"', '&quot;')))
})
