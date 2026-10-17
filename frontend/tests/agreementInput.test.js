import test from 'node:test'
import assert from 'node:assert/strict'
import { parseSourceIds } from '../src/paper/agreementInput.js'

test('source IDs retain commas and punctuation without rewriting provenance', () => {
  assert.deepEqual(parseSourceIds('folder,a.pdf\nsource://tenant/invoice?key=a,b'), [
    'folder,a.pdf', 'source://tenant/invoice?key=a,b',
  ])
})

test('source IDs use newline separators with whitespace and blank-line normalization', () => {
  assert.deepEqual(parseSourceIds('  first-id  \r\n\r\n second-id\n'), ['first-id', 'second-id'])
})

test('duplicate IDs remain visible to backend validation', () => {
  assert.deepEqual(parseSourceIds('same-id\nsame-id'), ['same-id', 'same-id'])
})

test('source ID input must be a string', () => {
  assert.throws(() => parseSourceIds(null), TypeError)
})
