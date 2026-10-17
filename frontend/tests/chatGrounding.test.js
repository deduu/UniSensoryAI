import test from 'node:test'
import assert from 'node:assert/strict'
import { appendGroundingDocument, resolveGroundingNavigation } from '../src/chat/grounding.js'

test('document Chat navigation selects only an identifier from the current scoped history', () => {
  const canonical = { id: 'current-document', content_text: 'Server content' }
  const navigation = resolveGroundingNavigation({ groundingDoc: { id: canonical.id, content_text: 'Stale route content' } }, [canonical])
  assert.deepEqual(navigation, { documentId: canonical.id, state: null })
  assert.deepEqual(canonical, { id: 'current-document', content_text: 'Server content' })
  assert.equal(resolveGroundingNavigation({ groundingDoc: { id: 'other-tenant-document' } }, [canonical]), null)
  assert.equal(resolveGroundingNavigation({ groundingDoc: { job_id: canonical.id } }, [canonical]), null)
  assert.equal(resolveGroundingNavigation({ groundingDoc: { id: { value: canonical.id } } }, [canonical]), null)
})

test('document handoff waits for scoped history hydration without trusting route content', () => {
  const state = { groundingDoc: { id: 'saved-document', content_text: 'Route-only content' } }
  assert.equal(resolveGroundingNavigation(state, []), null)
  assert.deepEqual(resolveGroundingNavigation(state, [{ id: 'saved-document' }]), { documentId: 'saved-document', state: null })
})

test('consuming the document handoff preserves other route state and prevents a manual deselection being reapplied', () => {
  const state = { groundingDoc: { id: 'document' }, from: '/documents', notice: 'Keep this' }
  const documents = [{ id: 'document' }]
  const navigation = resolveGroundingNavigation(state, documents)
  assert.deepEqual(navigation.state, { from: '/documents', notice: 'Keep this' })
  assert.equal(state.groundingDoc.id, 'document')
  assert.equal(resolveGroundingNavigation(navigation.state, documents), null)
  assert.equal(resolveGroundingNavigation(null, documents), null)
  assert.equal(resolveGroundingNavigation({}, documents), null)
})

test('appending a handed-off document preserves manual context and remains idempotent', () => {
  const manual = ['manually-selected']
  const selected = appendGroundingDocument(manual, 'clicked-document')
  assert.deepEqual(selected, ['manually-selected', 'clicked-document'])
  assert.deepEqual(manual, ['manually-selected'])
  assert.equal(appendGroundingDocument(selected, 'clicked-document'), selected)
})
