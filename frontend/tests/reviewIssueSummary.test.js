import test from 'node:test'
import assert from 'node:assert/strict'
import { groupReviewIssues } from '../src/paper/reviewIssueSummary.js'

const assessed = (code, field_path, extra = {}) => ({
  issue: { code, field_path, message: `Original ${code} diagnostic.` },
  status: 'attention', reason: 'Complete assessor reasoning.', citationStatus: 'unverified', pages: [], ...extra,
})

test('duplicate exact-field issues become one field-first group with every entry and source page retained', () => {
  const items = [assessed('invalid_evidence', '/fixed_rent', { pages: [4, 3] }), assessed('invalid_evidence', '/fixed_rent', { pages: [3, 9] }), assessed('field_review_incomplete', '/fixed_rent')]
  const before = structuredClone(items)
  const groups = groupReviewIssues(items, { fixed_rent: '327777777.00' })
  assert.equal(groups.length, 1)
  assert.equal(groups[0].label, 'Fixed rent')
  assert.equal(groups[0].valueState, 'present')
  assert.equal(groups[0].status, 'attention')
  assert.equal(groups[0].issueCount, 3)
  assert.deepEqual(groups[0].pages, [3, 4, 9])
  assert.equal(groups[0].summaries.length, 2)
  assert.equal(groups[0].summaries[0].count, 2)
  assert.equal(groups[0].items[0], items[0])
  assert.deepEqual(items, before)
})

test('missing external identifiers and optional source values have different next actions', () => {
  const groups = groupReviewIssues([assessed('field_review_incomplete', '/vendor_id'), assessed('field_review_incomplete', '/renewal_terms')], { vendor_id: null, renewal_terms: null })
  assert.equal(groups[0].valueState, 'missing')
  assert.match(groups[0].summaries[0].nextAction, /assigned master ID/i)
  assert.match(groups[0].summaries[0].why, /source ID not extracted.*master assignment is separate/i)
  assert.doesNotMatch(groups[0].summaries[0].why, /not assigned/i)
  assert.equal(groups[0].summaries[0].type, 'Source ID not extracted')
  assert.match(groups[1].summaries[0].nextAction, /needed.*leave unknown/i)
  assert.doesNotMatch(groups[1].summaries[0].nextAction, /external master/i)
})

test('an extracted identifier does not establish or replace the assigned master identity', () => {
  const [group] = groupReviewIssues([assessed('field_review_incomplete', '/store_id')], { store_id: 'PRINTED-LOCATION' })
  assert.equal(group.summaries[0].type, 'Source ID unconfirmed')
  assert.match(group.summaries[0].why, /extracted ID.*unconfirmed/i)
  assert.match(group.summaries[0].nextAction, /source.*assigned master ID separately/i)
})

test('filled, zero and false values never resolve unverified or semantic issues', () => {
  const items = [assessed('field_review_incomplete', '/fixed_rent'), assessed('invalid_evidence', '/enabled'), assessed('source_text_review_required', '/payment_schedule'), assessed('party_roles_review_required', '/party_roles')]
  const groups = groupReviewIssues(items, { fixed_rent: 0, enabled: false, payment_schedule: 'Present clause', party_roles: { landlord: 'Owner' } })
  assert.ok(groups.every(group => group.valueState === 'present' && group.status === 'attention'))
  assert.match(groups[0].summaries[0].why, /present.*unconfirmed/i)
  assert.match(groups[2].summaries[0].nextAction, /conditions.*exceptions/i)
  assert.match(groups[3].summaries[0].nextAction, /landlord.*tenant.*representation/i)
})

test('exact escaped pointers and collection indices stay separate from parents and siblings', () => {
  const groups = groupReviewIssues([assessed('invalid_evidence', '/a~1b/0/name~0raw'), assessed('invalid_evidence', '/a~1b/1/name~0raw'), assessed('source_text_review_required', '/a~1b')], { 'a/b': [{ 'name~raw': 'First' }, { 'name~raw': '' }] })
  assert.equal(groups.length, 3)
  assert.equal(groups[0].fieldPath, '/a~1b/0/name~0raw')
  assert.equal(groups[0].label, 'A/b · Item 1 · Name~raw')
  assert.equal(groups[0].value, 'First')
  assert.equal(groups[1].valueState, 'missing')
})

test('historical entries remain extraction history rather than successful fields', () => {
  const groups = groupReviewIssues([assessed('field_review_revised', '/fixed_rent', { status: 'history', citationStatus: 'verified' })], { fixed_rent: '100' })
  assert.equal(groups[0].status, 'history')
  assert.equal(groups[0].summaries[0].type, 'Extraction history')
  assert.doesNotMatch(groups[0].summaries[0].why, /passed|resolved|success/i)
  assert.match(groups[0].summaries[0].nextAction, /does not confirm/i)
})

test('unknown and document-level diagnostics stay visible with complete retained entries', () => {
  const items = [assessed('future_issue', undefined), { issue: 'Original legacy warning', status: 'attention', pages: [], reason: 'Legacy reason' }, assessed('future_issue', '/unknown')]
  const groups = groupReviewIssues(items, {})
  assert.equal(groups.length, 2)
  assert.equal(groups[0].label, 'Document review')
  assert.equal(groups[0].issueCount, 2)
  assert.deepEqual(groups.flatMap(group => group.items), items)
  assert.ok(groups.every(group => group.summaries.every(summary => summary.why && summary.nextAction)))
})

test('mixed status and empty collections remain explicit without changing assessor results', () => {
  const groups = groupReviewIssues([assessed('source_text_review_required', '/other_key_terms'), assessed('field_review_revised', '/other_key_terms', { status: 'history' })], { other_key_terms: [] })
  assert.equal(groups[0].status, 'mixed')
  assert.equal(groups[0].valueState, 'empty')
  assert.equal(groups[0].items[0].status, 'attention')
  assert.equal(groups[0].items[1].status, 'history')
})

test('overview reasons and actions fit brief scan-friendly sentences', () => {
  const codes = ['field_review_incomplete', 'invalid_evidence', 'source_text_review_required', 'party_roles_review_required', 'source_amount_discrepancy', 'installment_schedule_source_unresolved', 'source_text_incomplete', 'future_issue']
  const groups = groupReviewIssues(codes.map((code, index) => assessed(code, index === 0 ? '/vendor_id' : `/field_${index}`)))
  for (const group of groups) for (const summary of group.summaries) {
    assert.ok(summary.why.length <= 72, summary.why)
    assert.ok(summary.nextAction.length <= 80, summary.nextAction)
  }
})
