import test from 'node:test'
import assert from 'node:assert/strict'
import { assessWarnings } from '../src/paper/warningReview.js'

const issue = (code, field_path = '/amount') => ({ code, field_path, message: 'Retained diagnostic' })
const record = { result: { document: { document_id: 'original', pages: [
  { page_number: 2, text_blocks: [{ block_id: 'term', text: 'Annual rent is 125.\n Pay in advance.' }], images: [], tables: [] },
  { page_number: 4, text_blocks: [{ block_id: 'owner', text: 'The landlord is Owner Ltd.' }], images: [], tables: [] },
] } } }
const citation = (path = '/amount', source_ids = ['term'], quote = 'Annual rent is 125.') => ({ document_id: 'original', evidence: { field_path: path, source_ids, quote } })
const assess = options => assessWarnings({ record, data: { amount: '125' }, evidence: [citation()], ...options })

test('rejected citation diagnostics become history only with a current exact traceable citation', () => {
  const warning = issue('invalid_evidence')
  const result = assess({ warnings: [warning] })
  assert.deepEqual(result.counts, { attention: 0, history: 1, total: 1 })
  assert.equal(result.history[0].issue, warning)
  assert.equal(result.history[0].citationStatus, 'verified')
  assert.deepEqual(result.history[0].pages, [2])
  assert.match(result.history[0].reason, /traceab|citation/i)
  assert.match(result.history[0].reason, /semantic|meaning|correctness/i)
})

test('foreign, guessed, ambiguous, blank and nonliteral citations keep diagnostics active', () => {
  const ambiguous = structuredClone(record)
  ambiguous.result.document.pages[1].text_blocks.push({ block_id: 'term', text: 'Annual rent is 125.' })
  for (const options of [
    { record: null }, { evidence: [] },
    { evidence: [{ ...citation(), document_id: 'foreign' }] },
    { evidence: [citation('/amount', ['p2-guessed'])] },
    { evidence: [citation('/amount', ['term', 'missing'])] },
    { evidence: [citation('/amount', ['term'], '')] },
    { evidence: [citation('/amount', ['term'], 'Annual rent is 999.')] },
    { evidence: [citation('/amount', ['term'], 'annual rent is 125.')] },
    { record: ambiguous }, { data: { amount: null } }, { data: {} },
    { data: { amount: { currency: 'IDR' } } }, { data: { amount: ['125'] } },
  ]) {
    const result = assess({ warnings: [issue('invalid_evidence')], ...options })
    assert.equal(result.counts.attention, 1, JSON.stringify(options))
    assert.equal(result.counts.history, 0)
  }
})

test('parent, child and sibling citations cannot retire an exact field diagnostic', () => {
  for (const field of ['/amount/0', '/amount_extra', '/amount2', '/']) {
    assert.equal(assess({ evidence: [citation(field)], warnings: [issue('invalid_evidence')] }).counts.attention, 1)
  }
})

test('one good citation cannot conceal another invalid citation on the same field', () => {
  const result = assess({ evidence: [citation(), citation('/amount', ['missing'])], warnings: [issue('invalid_evidence')] })
  assert.equal(result.counts.attention, 1)
})

test('literal whitespace normalization preserves raw quotes and cross-page evidence', () => {
  const evidence = [citation('/amount', ['term'], '125. Pay in advance.'), citation('/amount', ['owner'], 'Owner Ltd.')]
  const before = structuredClone(evidence)
  const result = assess({ evidence, warnings: [issue('invalid_evidence')] })
  assert.equal(result.counts.history, 1)
  assert.deepEqual(result.history[0].pages, [2, 4])
  assert.deepEqual(evidence, before)
})

test('source and party semantics remain current review requirements despite valid literal citations', () => {
  const warnings = ['source_text_review_required', 'party_roles_review_required', 'field_review_incomplete', 'party_vendor_mismatch', 'missing_evidence', 'unknown_new_code'].map(code => issue(code))
  const result = assess({ warnings })
  assert.deepEqual(result.attention.map(item => item.issue), warnings)
  assert.equal(result.history.length, 0)
})

test('revision and lineage notices are historical events without implying approval', () => {
  const warnings = ['field_review_revised', 'party_chain_source_reviewed', 'prior_terms_retained'].map(code => issue(code))
  const result = assess({ warnings, record: null })
  assert.equal(result.counts.history, 3)
  assert.ok(result.history.every(item => /review|approval/i.test(item.reason)))
})

test('retained automatic-candidate diagnostics are explicit immutable history after regrouping', () => {
  const retained = {
    code: 'source_candidate_diagnostic_retained',
    field_path: '/other_key_terms/7',
    message: 'Original invalid_evidence at /other_key_terms/7: rejected quote; source job automatic-job.',
  }
  const options = {
    record,
    data: { other_key_terms: ['Current complete source clause.'] },
    warnings: [retained],
    evidence: [],
  }
  const before = structuredClone(options)
  const result = assessWarnings(options)
  assert.deepEqual(result.counts, { attention: 0, history: 1, total: 1 })
  assert.equal(result.history[0].issue, retained)
  assert.match(result.history[0].reason, /earlier automatic candidate/i)
  assert.match(result.history[0].reason, /index.*no longer/i)
  assert.match(result.history[0].reason, /does not establish.*coverage.*correctness/i)
  assert.deepEqual(options, before)
})

test('candidate lineage never retires current narrative, party, unknown or raw citation diagnostics', () => {
  const retained = issue('source_candidate_diagnostic_retained', '/other_key_terms/7')
  const current = [
    issue('source_text_review_required'),
    issue('party_roles_review_required'),
    issue('unknown_candidate_warning'),
    issue('invalid_evidence', '/other_key_terms/7'),
  ]
  const warnings = [retained, ...current]
  const before = structuredClone(warnings)
  const result = assess({ warnings })
  assert.deepEqual(result.history.map(item => item.issue), [retained])
  assert.deepEqual(result.attention.map(item => item.issue), current)
  assert.match(result.history[0].reason, /narrative.*party.*review.*approval/i)
  assert.deepEqual(warnings, before)
})

test('escaped pointers, zero and false remain exact supported values; prototype properties stay absent', () => {
  for (const [path, data] of [['/a~1b/~0c', { 'a/b': { '~c': 0 } }], ['/flag', { flag: false }]]) {
    assert.equal(assess({ data, evidence: [citation(path)], warnings: [issue('invalid_evidence', path)] }).counts.history, 1)
  }
  assert.equal(assess({ evidence: [citation('/toString')], warnings: [issue('invalid_evidence', '/toString')] }).counts.attention, 1)
})

test('source images and tables without stored text cannot establish a literal quotation', () => {
  const visual = structuredClone(record)
  visual.result.document.pages[0].images.push({ asset_id: 'image' })
  visual.result.document.pages[0].tables.push({ table_id: 'table', rows: [['Annual rent is 125.']] })
  for (const id of ['image', 'table']) assert.equal(assess({ record: visual, evidence: [citation('/amount', [id])], warnings: [issue('invalid_evidence')] }).counts.attention, 1)
})

test('projection keeps every retained issue, accepts legacy strings, and never changes inputs', () => {
  const warnings = [issue('invalid_evidence'), issue('invalid_evidence'), 'Legacy warning', { code: 'invalid_evidence' }]
  const options = { record, evidence: [citation()], data: { amount: '125' }, warnings }
  const before = structuredClone(options)
  const result = assessWarnings(options)
  assert.equal(result.items.length, 4)
  assert.deepEqual(result.counts, { attention: 2, history: 2, total: 4 })
  assert.deepEqual(options, before)
  assert.deepEqual(assessWarnings({}).counts, { attention: 0, history: 0, total: 0 })
})

test('unsaved field edits reopen citation diagnostics against the explicit saved baseline', () => {
  const warnings = [issue('invalid_evidence'), issue('field_review_revised')]
  const result = assess({ warnings, baselineData: { amount: '125' }, data: { amount: '999' } })
  assert.deepEqual(result.counts, { attention: 1, history: 1, total: 2 })
  assert.match(result.attention[0].reason, /edited/i)
  assert.equal(assess({ warnings: warnings.slice(0, 1), baselineData: { amount: '125' } }).counts.history, 1)
})

test('even a literally cited wrong-role value cannot clear the separate party review requirement', () => {
  const result = assess({ data: { vendor_name: 'Owner Ltd.' }, evidence: [citation('/vendor_name', ['owner'], 'Owner Ltd.')], warnings: [issue('invalid_evidence', '/vendor_name'), issue('party_roles_review_required', '/vendor_name')] })
  assert.equal(result.history[0].issue.code, 'invalid_evidence')
  assert.equal(result.attention[0].issue.code, 'party_roles_review_required')
})

test('text IDs colliding with visual IDs are ambiguous, and unavailable evidence never looks verified', () => {
  const collision = structuredClone(record)
  collision.result.document.pages[0].images.push({ asset_id: 'term' })
  assert.equal(assess({ record: collision, warnings: [issue('invalid_evidence')] }).counts.attention, 1)
  const noSource = assess({ record: null, warnings: [issue('invalid_evidence')] })
  assert.equal(noSource.attention[0].citationStatus, 'unavailable')
  assert.deepEqual(noSource.attention[0].pages, [])
})

test('aggregate semantic review retains all child source pages without treating parent evidence as leaf support', () => {
  const evidence = [citation('/parties/0/name'), citation('/parties/1/name', ['owner'], 'Owner Ltd.')]
  const result = assess({ evidence, warnings: [issue('party_roles_review_required', '/parties')] })
  assert.equal(result.counts.attention, 1)
  assert.deepEqual(result.attention[0].pages, [2, 4])
  assert.equal(result.attention[0].citationStatus, 'verified')
})
