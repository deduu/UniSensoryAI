import test, { after, before } from 'node:test'
import assert from 'node:assert/strict'
import { fileURLToPath } from 'node:url'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'
import react from '@vitejs/plugin-react'
import { groupReviewIssues } from '../src/paper/reviewIssueSummary.js'

let server
let ReviewIssueList
before(async () => {
  server = await createServer({ root: fileURLToPath(new URL('..', import.meta.url)), configFile: false, plugins: [react()], server: { middlewareMode: true, hmr: false, watch: null } })
  ReviewIssueList = (await server.ssrLoadModule('/src/components/paper/ReviewIssueList.jsx')).default
})
after(async () => { await server?.close() })

const issue = (code, field_path, extra = {}) => ({ issue: { code, field_path, message: `Full original ${code} message.` }, status: 'attention', reason: 'Complete original assessor reasoning.', citationStatus: 'unverified', pages: [3, 8], ...extra })
const render = (items, data = {}, props = {}) => renderToStaticMarkup(createElement(ReviewIssueList, { groups: groupReviewIssues(items, data), data, record: {}, onNavigate: () => {}, onInspect: () => {}, ...props }))

test('compact field-first issues retain every diagnostic in collapsed details and all source shortcuts', () => {
  const html = render([issue('invalid_evidence', '/fixed_rent'), issue('field_review_incomplete', '/fixed_rent')], { fixed_rent: '327777777.00', currency: 'IDR' })
  assert.match(html, /<h4>Fixed rent<\/h4>/)
  assert.match(html, /Next:/)
  assert.match(html, /Value needs confirmation/)
  assert.match(html, /Details · 2 retained entries/)
  assert.match(html, /Full original invalid_evidence message/)
  assert.match(html, /Full original field_review_incomplete message/)
  assert.match(html, /Complete original assessor reasoning/)
  assert.match(html, /Citation requires review/)
  assert.match(html, /Exact retained entry \(JSON\)/)
  assert.match(html, />p\. 3<\/button>/)
  assert.match(html, />p\. 8<\/button>/)
  assert.match(html, /Review field/)
  assert.doesNotMatch(html, /<strong>Source check\.<\/strong>/)
  assert.match(html, /IDR/)
  assert.doesNotMatch(html, /<details[^>]*\bopen(?:=|>|\s)/)
})

test('history is labelled extraction history and never presented as passed fields', () => {
  const html = render([issue('field_review_revised', '/vendor_name', { status: 'history', citationStatus: 'verified' })], { vendor_name: 'Owner' })
  assert.match(html, /Extraction history/)
  assert.match(html, /does not confirm current data/)
  assert.doesNotMatch(html, /Passed|Resolved|Value needs confirmation/)
})

test('document diagnostics and untrusted text remain accessible without activating content', () => {
  const html = render([{ issue: '<script>alert(1)</script>', status: 'attention', reason: 'Unknown issue', pages: [], citationStatus: 'unavailable' }])
  assert.match(html, /Document review/)
  assert.match(html, /&lt;script&gt;/)
  assert.match(html, /Original source unavailable/)
  assert.doesNotMatch(html, /<script\b|>Review field</)
})
