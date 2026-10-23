import test from 'node:test'
import assert from 'node:assert/strict'
import { isOlderWorkspaceIntent, resolveWorkspaceSelection } from '../src/paper/workspaceSelection.js'

const agreement = version => ({ agreement_id: 'agreement', tenant_id: 'tenant', version_number: version })
const invoiceCase = version => ({ case_id: 'case', tenant_id: 'tenant', version_number: version })

test('only an older numeric navigation intent is superseded, preserving legacy prop handoffs', () => {
  assert.equal(isOlderWorkspaceIntent(2, 3), true)
  assert.equal(isOlderWorkspaceIntent(3, 2), false)
  assert.equal(isOlderWorkspaceIntent(3, 3), false)
  for (const [request, other] of [[undefined, 3], [2, undefined], [null, 3], [2, null], ['2', 3], [2, '3'], [{}, 3], [NaN, 3], [2, Infinity], [-1, 3]]) {
    assert.equal(isOlderWorkspaceIntent(request, other), false)
  }
})

test('exact agreement selection stays historical while latest eligibility comes from history', async () => {
  const history = [agreement(7), agreement(6)]
  const before = structuredClone(history)
  const calls = []
  const api = {
    agreementVersions: async (...args) => { calls.push(['history', ...args]); return history },
    agreementVersion: async (...args) => { calls.push(['exact', ...args]); return agreement(2) },
  }
  const result = await resolveWorkspaceSelection({ api, kind: 'agreement', id: 'agreement', versionNumber: 2, limit: 20 })
  assert.deepEqual(result, { record: agreement(2), history, latest: 7 })
  assert.deepEqual(history, before)
  assert.deepEqual(calls, [['history', 'agreement', { limit: 20, offset: 0 }], ['exact', 'agreement', 2]])
})

test('opening the latest case does not perform a separate exact request', async () => {
  const history = [invoiceCase(3), invoiceCase(2)]
  const api = { caseVersions: async () => history, caseVersion: async () => assert.fail('Unexpected exact lookup') }
  assert.deepEqual(await resolveWorkspaceSelection({ api, kind: 'case', id: 'case' }), { record: history[0], history, latest: 3 })
})

test('exact case 404 propagates without falling back to the latest snapshot', async () => {
  const missing = Object.assign(new Error('Version not found'), { status: 404 })
  const api = { caseVersions: async () => [invoiceCase(3)], caseVersion: async () => { throw missing } }
  await assert.rejects(resolveWorkspaceSelection({ api, kind: 'case', id: 'case', versionNumber: 1 }), error => error === missing)
})

test('selection rejects mismatched IDs, versions, tenant snapshots and empty history', async () => {
  for (const record of [agreement(4), { ...agreement(2), agreement_id: 'other' }, { ...agreement(2), tenant_id: 'other' }]) {
    await assert.rejects(resolveWorkspaceSelection({ api: { agreementVersions: async () => [agreement(7)], agreementVersion: async () => record }, kind: 'agreement', id: 'agreement', versionNumber: 2 }), /requested|tenant/i)
  }
  for (const history of [[], [{ ...agreement(7), agreement_id: 'other' }], [{ ...agreement(7), version_number: 0 }]]) {
    await assert.rejects(resolveWorkspaceSelection({ api: { agreementVersions: async () => history }, kind: 'agreement', id: 'agreement' }), /history|requested/i)
  }
})

test('invalid selection parameters are rejected before any API request', async () => {
  const api = { agreementVersions: async () => assert.fail('Invalid input must not request history') }
  for (const changes of [{ kind: 'document' }, { id: '' }, { versionNumber: 0 }, { versionNumber: '2' }, { limit: 101 }]) {
    await assert.rejects(resolveWorkspaceSelection({ api, kind: 'agreement', id: 'agreement', ...changes }), /selection|version|limit/i)
  }
})
