import test, { before } from 'node:test'
import assert from 'node:assert/strict'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'
import vm from 'node:vm'
import { build } from 'esbuild'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'

let Values
let ComparisonResult
before(async () => {
  const component = new URL('../src/components/paper/ReconciliationWorkspace.jsx', import.meta.url)
  const compiled = await build({ entryPoints: [fileURLToPath(component)], bundle: true, write: false, platform: 'node', format: 'cjs', jsx: 'automatic', packages: 'external' })
  const module = { exports: {} }
  vm.runInNewContext(compiled.outputFiles[0].text, { module, exports: module.exports, require: createRequire(component) })
  Values = module.exports.Values
  ComparisonResult = module.exports.ComparisonResult
})

const render = values => renderToStaticMarkup(createElement(Values, { values }))

test('literal equality and unevaluated saved results are visibly separate', () => {
  const row = { status: 'unavailable', findings: [], valueComparison: { status: 'equal', label: 'Values equal' } }
  const html = renderToStaticMarkup(createElement(ComparisonResult, { row, ready: true, referenceOnly: true }))
  assert.match(html, /Field values/)
  assert.match(html, /Values equal/)
  assert.match(html, /Saved result/)
  assert.match(html, /Not assessed against contract/)
  assert.doesNotMatch(html, /Coverage not verified|Matched/)
})

test('saved blocking findings remain prominent beside literal equality and loading hides derived values', () => {
  const row = { status: 'blocking', findings: [{ code: 'currency_mismatch', message: 'Saved finding', severity: 'blocking' }], valueComparison: { status: 'equal', label: 'Values equal' } }
  const html = renderToStaticMarkup(createElement(ComparisonResult, { row, ready: true, referenceOnly: true }))
  assert.match(html, /Issue reported/)
  assert.match(html, /Saved finding/)
  assert.match(html, /Values equal/)
  const loading = renderToStaticMarkup(createElement(ComparisonResult, { row, ready: false, referenceOnly: true }))
  assert.match(loading, /Loading reference/)
  assert.doesNotMatch(loading, /Values equal/)
})

test('long comparison narratives use a closed named disclosure with exact complete content', () => {
  const text = '\n  Source payment clause & <conditions>\n'.repeat(12) + '\tExact final clause.  '
  const values = [{ label: 'Source payment schedule', value: text }]
  const before = structuredClone(values)
  const html = render(values)
  assert.match(html, /<details\b/)
  assert.doesNotMatch(html, /<details[^>]*\sopen(?:=|\s|>)/)
  assert.match(html, /<summary[^>]*>Read full source payment schedule<\/summary>/)
  const preview = Array.from(text).slice(0, 160).join('') + '…'
  const escape = value => value.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
  assert.ok(html.includes(escape(preview)))
  const disclosure = html.slice(html.indexOf('<details'), html.indexOf('</details>'))
  assert.ok(disclosure.includes(escape(text)))
  assert.match(disclosure, /whitespace-pre-wrap/)
  assert.deepEqual(values, before)
})

test('short boundary values, money, unknowns and numeric identifiers remain inline', () => {
  const values = [
    { label: 'Boundary text', value: 'a'.repeat(320) },
    { label: 'Account', value: '000123' },
    { label: 'Unknown policy', value: null },
    { label: 'Amount', value: '1'.repeat(321) + '.03', monetary: true, currency: 'IDR' },
  ]
  const before = structuredClone(values)
  const html = render(values)
  assert.doesNotMatch(html, /<details\b|Read full/)
  assert.ok(html.includes('a'.repeat(320)))
  assert.match(html, />000123</)
  assert.match(html, />Unknown</)
  assert.deepEqual(values, before)
})
