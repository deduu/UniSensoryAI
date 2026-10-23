import test, { after, before } from 'node:test'
import assert from 'node:assert/strict'
import { fileURLToPath } from 'node:url'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'
import react from '@vitejs/plugin-react'

let server
let WorkspaceIndexItems
let DocumentWorkflowActions
before(async () => {
  server = await createServer({ root: fileURLToPath(new URL('..', import.meta.url)), configFile: false, plugins: [react()], server: { middlewareMode: true, hmr: false, watch: null } })
  ;({ WorkspaceIndexItems, DocumentWorkflowActions } = await server.ssrLoadModule('/src/components/paper/WorkspaceIndex.jsx'))
})
after(async () => { await server?.close() })

test('case index exposes the exact selected contract version and issues without implying billing authority', () => {
  const item = { case_id: 'case', version_number: 2, invoice_number: 'INV-7', identity: { contract_number: '65' }, vendor_name: 'Owner', status: 'incomplete', blocking_count: 4, review_count: 1, association: { kind: 'confirmed', agreement_id: 'contract', version_number: 6 }, next_action: 'resolve_discrepancies' }
  const html = renderToStaticMarkup(createElement(WorkspaceIndexItems, { items: [item], onOpenCase: () => {} }))
  assert.match(html, /INV-7/)
  assert.match(html, /Contract 65 · v6/)
  assert.match(html, /Reviewer-confirmed association/)
  assert.match(html, /4 blocking issues · 1 to review/)
  assert.match(html, /Review discrepancies/)
  assert.doesNotMatch(html, /Approved contract|Payment eligible|Matched/)
})

test('legacy identity links remain visibly distinct from confirmed contract associations', () => {
  const html = renderToStaticMarkup(createElement(WorkspaceIndexItems, { items: [{ case_id: 'legacy', version_number: 1, identity: { contract_number: '65' }, status: 'needs_review', blocking_count: 0, review_count: 1, association: { kind: 'legacy_identity', agreement_id: 'a' } }] }))
  assert.match(html, /Legacy identity reference · confirmation required/)
  assert.doesNotMatch(html, /Reviewer-confirmed/)
})

test('multiple source links demand explicit exact-version choice and identify historical revisions', () => {
  const document = { workflow_status: 'agreement_draft', workflow_links_total: 12, workflow_links: [{ kind: 'agreement', id: 'a', version_number: 6, status: 'draft', is_latest: true }, { kind: 'agreement', id: 'a', version_number: 4, status: 'approved', is_latest: false }] }
  const html = renderToStaticMarkup(createElement(DocumentWorkflowActions, { document, onAction: () => {} }))
  assert.match(html, /12 saved version links · choose a version/)
  assert.match(html, /Agreement v4 · Approved · Historical version/)
  assert.match(html, /Showing 2 of 12 links/)
  assert.doesNotMatch(html, /<details[^>]*\bopen(?:=|>|\s)/)
})

test('document filenames are escaped and retained logs are separate from current workflow status', () => {
  const html = renderToStaticMarkup(createElement(WorkspaceIndexItems, { mode: 'documents', items: [{ job_id: 'job', filename: '<img src=x onerror=alert(1)>.pdf', schema_name: 'rent_invoice', status: 'completed', workflow_status: 'ready_for_review', warning_count: 20, workflow_links_total: 0, next_action: 'review_invoice' }] }))
  assert.match(html, /&lt;img/)
  assert.match(html, /20 retained log entries/)
  assert.match(html, /Ready for review/)
  assert.doesNotMatch(html, /<img\b|20 unresolved|20 warnings/)
})

test('unindexed legacy uploads do not claim there are no saved workflows', () => {
  const html = renderToStaticMarkup(createElement(WorkspaceIndexItems, { mode: 'documents', items: [{ job_id: 'legacy', filename: 'Old invoice.pdf', schema_name: 'rent_invoice', status: 'completed', workflow_status: 'ready_for_review', workflow_links_resolved: false, workflow_links_total: 0, next_action: 'review_invoice' }] }))
  assert.match(html, /Saved links unavailable/)
  assert.match(html, /source index needs repair/)
  assert.doesNotMatch(html, /No saved workflow version yet|Extraction is ready/)
})
