import test from 'node:test'
import assert from 'node:assert/strict'
import { documentWorkflowActions, nextActionLabel, workspaceQuery, workspaceStatus, createWorkspaceRequestGate } from '../src/paper/workspaceNavigation.js'

test('workspace queries remain bounded and keep confirmed contract filtering explicit', () => {
  assert.deepEqual(workspaceQuery({ mode: 'cases', q: '  Tanjung  ', status: 'incomplete', offset: 20, agreementFilter: { agreement_id: 'saved-contract' } }), {
    q: 'Tanjung', status: 'incomplete', limit: 20, offset: 20, agreement_id: 'saved-contract', association_kind: 'confirmed',
  })
  assert.deepEqual(workspaceQuery({ mode: 'documents', q: '', status: '', offset: 0, archived: true, agreementFilter: { agreement_id: 'ignored' } }), { q: '', limit: 20, offset: 0, archived: true })
  assert.deepEqual(workspaceQuery({ mode: 'documents', status: 'agreement_draft' }), { q: '', workflow_status: 'agreement_draft', limit: 20, offset: 0, archived: false })
})

test('action labels describe review boundaries without promising approval or a match', () => {
  assert.equal(nextActionLabel('resolve_discrepancies'), 'Review discrepancies')
  assert.equal(nextActionLabel('review_agreement'), 'Review agreement')
  assert.equal(nextActionLabel('wait_for_extraction'), 'View extraction progress')
  assert.equal(nextActionLabel('unknown'), 'Open workspace')
  assert.equal(workspaceStatus('ready_for_review'), 'Ready for review')
})

test('document navigation preserves every exact saved target and never chooses between revisions', () => {
  const links = [
    { kind: 'agreement', id: 'a', version_number: 3, status: 'draft', is_latest: true },
    { kind: 'agreement', id: 'a', version_number: 2, status: 'approved', is_latest: false },
  ]
  const actions = documentWorkflowActions({ workflow_links: links, workflow_links_total: 2 })
  assert.equal(actions.primary, null)
  assert.equal(actions.needsChoice, true)
  assert.deepEqual(actions.links, links)
  assert.equal(links[1].is_latest, false)
  assert.equal(documentWorkflowActions({ workflow_links: [links[0]], workflow_links_total: 1 }).primary, links[0])
  assert.equal(documentWorkflowActions({ workflow_links: [links[0]], workflow_links_total: 8 }).primary, null)
  assert.equal(documentWorkflowActions({ workflow_links: [], workflow_links_total: 0 }).needsChoice, false)
})

test('stale list requests and disposed scopes cannot replace current results', () => {
  const gate = createWorkspaceRequestGate()
  const old = gate.start()
  const current = gate.start()
  assert.equal(gate.isCurrent(old), false)
  assert.equal(gate.isCurrent(current), true)
  gate.invalidate()
  assert.equal(gate.isCurrent(current), false)
})
