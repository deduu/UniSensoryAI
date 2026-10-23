import test from 'node:test'
import assert from 'node:assert/strict'
import { appendPointer, canEditStringList, editStringList } from '../src/components/paper/readableFields.js'

test('clause edits preserve exact whitespace, order, empty strings and untouched values', () => {
  const original = ['  first\r\nclause ', '', 'third']
  assert.deepEqual(editStringList(original, { type: 'replace', index: 1, text: '\n second  ' }), ['  first\r\nclause ', '\n second  ', 'third'])
  assert.deepEqual(editStringList(original, { type: 'remove', index: 1 }), ['  first\r\nclause ', 'third'])
  assert.deepEqual(editStringList(original, { type: 'append' }), ['  first\r\nclause ', '', 'third', ''])
  assert.deepEqual(original, ['  first\r\nclause ', '', 'third'])
})

test('unknown and empty clause lists are different and new items are explicit edits', () => {
  assert.deepEqual(editStringList(null, { type: 'append' }), [''])
  assert.deepEqual(editStringList([''], { type: 'remove', index: 0 }), [])
  assert.equal(canEditStringList({ type: 'array', items: { type: 'string' } }, null), true)
  assert.equal(canEditStringList({ type: 'array', items: { type: 'string' } }, []), true)
  assert.equal(canEditStringList({ type: 'array', items: { type: 'object' } }, []), false)
  assert.equal(canEditStringList({ type: 'array', items: { type: 'string' } }, ['text', null]), false)
})

test('list edits reject invalid indices instead of silently changing another clause', () => {
  assert.throws(() => editStringList(['clause'], { type: 'replace', index: 3, text: 'wrong' }))
  assert.throws(() => editStringList(['clause'], { type: 'remove', index: -1 }))
  assert.throws(() => editStringList(['clause'], { type: 'replace', index: 0, text: null }))
  assert.equal(appendPointer('/a~1b', 'x~/y'), '/a~1b/x~0~1y')
})
