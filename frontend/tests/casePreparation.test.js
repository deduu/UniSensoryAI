import test, { before, after } from 'node:test'
import assert from 'node:assert/strict'
import { fileURLToPath } from 'node:url'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'
import react from '@vitejs/plugin-react'

let server
let ReadinessChecklist
let DocumentDraftCards
let CasePreparation
before(async () => {
  server = await createServer({ root: fileURLToPath(new URL('..', import.meta.url)), configFile: false, plugins: [react()], server: { middlewareMode: true, hmr: false, watch: null } })
  ;({ default: CasePreparation, ReadinessChecklist } = await server.ssrLoadModule('/src/components/paper/CasePreparation.jsx'))
  ;({ DocumentDraftCards } = await server.ssrLoadModule('/src/components/paper/DocumentDraftLibrary.jsx'))
})
after(async () => { await server?.close() })

test('readiness presents mandatory, conditional and optional fields without equating optional with an error', () => {
  const readiness = { ready: false, policy_id: 'local-rent', policy_version: 2, checks: [
    { key: 'number', label: 'Invoice number', requirement: 'required', status: 'satisfied', reason: 'Present' },
    { key: 'coverage', label: 'Service period', requirement: 'required', status: 'missing', reason: 'Enter verified service dates or an approved allocation.' },
    { key: 'tax', label: 'Tax reference', requirement: 'conditional', status: 'not_applicable', reason: 'This condition does not apply.' },
    { key: 'memo', label: 'Memo', requirement: 'optional', status: 'missing', reason: 'May be left blank.' },
  ] }
  const html = renderToStaticMarkup(createElement(ReadinessChecklist, { readiness }))
  assert.match(html, /Required/)
  assert.match(html, /Conditional/)
  assert.match(html, /Optional/)
  assert.match(html, /Not applicable/)
  assert.match(html, /May be left blank/)
  assert.match(html, /Enter verified service dates/)
  assert.match(html, /local-rent/)
  assert.doesNotMatch(html, /Payment eligible|Approved for payment/)
})

test('reconciliation requires an explicit fresh readiness response', () => {
  const html = renderToStaticMarkup(createElement(CasePreparation, { api: {}, package: { invoice: { source_document_id: 'pdf', fields: { invoice_number: 'INV-1' } } }, selection: { invoice: { draft_id: 'i', version_number: 1 } }, onRun: () => {} }))
  assert.match(html, /Check readiness/)
  assert.match(html, /Run reconciliation/)
  assert.match(html, /disabled=""[^>]*>Run reconciliation/)
  assert.match(html, /Check readiness after selecting/)
  assert.doesNotMatch(html, /Reconcile package/)
})

test('draft cards show an exact saved version and prepare only reviewed rent invoices', () => {
  const base = { draft_id: 'i', version_number: 4, role: 'rent_invoice', document: { fields: { invoice_number: '<INV-4>', vendor_name: 'Owner' } } }
  const html = renderToStaticMarkup(createElement(DocumentDraftCards, { items: [{ ...base, status: 'reviewed' }, { ...base, draft_id: 'j', status: 'draft' }, { ...base, draft_id: 'k', role: 'tax_invoice', status: 'reviewed' }], onOpen: () => {}, onPrepare: () => {} }))
  assert.match(html, /&lt;INV-4&gt;/)
  assert.match(html, /v4/)
  assert.equal((html.match(/>Prepare case</g) || []).length, 1)
  assert.equal((html.match(/>Review draft</g) || []).length, 3)
})

test('long unresolved check lists expose a compact first group and expandable remainder', () => {
  const readiness = { ready: false, checks: Array.from({ length: 10 }, (_, index) => ({ key: `field-${index}`, label: `Field ${index}`, requirement: 'required', status: 'missing', blocking: true, reason: 'Provide this field.' })) }
  const html = renderToStaticMarkup(createElement(ReadinessChecklist, { readiness }))
  assert.match(html, /2 more checks need attention/)
  assert.doesNotMatch(html, /<details[^>]*\bopen(?:=|>|\s)/)
})
