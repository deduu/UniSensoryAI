import test from 'node:test'
import assert from 'node:assert/strict'
import { filterFieldValues } from '../src/paper/fieldReview.js'

test('field search matches readable names and nested values without changing canonical data', () => {
  const data = { lease_start_date: '2027-01-05', other_key_terms: ['Clause A', 'Force majeure'], settings: { rate: '0.1' }, unknown: null }
  const before = structuredClone(data)
  assert.deepEqual(filterFieldValues(data, 'LEASE START').map(item => item.fieldPath), ['/lease_start_date'])
  assert.deepEqual(filterFieldValues(data, '  MAJEURE ').map(item => item.fieldPath), ['/other_key_terms'])
  assert.deepEqual(filterFieldValues(data, '0.1').map(item => item.fieldPath), ['/settings'])
  assert.deepEqual(data, before)
})

test('unfiltered fields preserve order, null, false, zero, empty arrays and escaped source pointers', () => {
  const data = { 'source/key~1': 0, reviewed: false, missing: null, clauses: [] }
  const fields = filterFieldValues(data, '')
  assert.deepEqual(fields, [
    { fieldPath: '/source~1key~01', value: 0 },
    { fieldPath: '/reviewed', value: false },
    { fieldPath: '/missing', value: null },
    { fieldPath: '/clauses', value: [] },
  ])
  assert.equal(filterFieldValues(data, 'false')[0].value, false)
})

test('empty and non-object documents do not fabricate searchable fields', () => {
  assert.deepEqual(filterFieldValues(undefined, 'rent'), [])
  assert.deepEqual(filterFieldValues(null, ''), [])
  assert.deepEqual(filterFieldValues([], ''), [])
  assert.deepEqual(filterFieldValues({ contract_number: '65' }, 'missing'), [])
})
