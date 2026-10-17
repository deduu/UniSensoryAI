import test from 'node:test'
import assert from 'node:assert/strict'
import { jobScope, jobsForScope, normalizeHistoryJob, discardLegacyJobCache, reconcileHistorySnapshot } from '../src/jobs/history.js'

test('job histories are invisible across tenants, accounts, backends and logout', () => {
  const a = jobScope({ user_id: 'reviewer', tenant_id: 'tenant-a' }, '')
  const state = { scope: a, jobs: [{ job_id: 'private' }] }
  assert.equal(jobsForScope(state, a).length, 1)
  for (const scope of [null, jobScope({ user_id: 'reviewer', tenant_id: 'tenant-b' }, ''), jobScope({ user_id: 'other', tenant_id: 'tenant-a' }, ''), jobScope({ user_id: 'reviewer', tenant_id: 'tenant-a' }, 'https://other')]) assert.deepEqual(jobsForScope(state, scope), [])
  assert.equal(jobScope(null, ''), null)
})

test('history normalization restores server filenames and statuses without retaining model credentials', () => {
  const job = normalizeHistoryJob({ job_id: '1', status: 'COMPLETED', file_path: 'C:\\uploads\\aabbccdd-1111-2222-3333-444455556666_Scan.pdf', meta: { api_keys: { secret: 'value' }, model_id: 'host-model', file_size: 100, error: 'failed', workflow: 'paper_extraction' }, documents: [{ id: 'doc' }] })
  assert.equal(job.filename, 'Scan.pdf')
  assert.equal(job.status, 'completed')
  assert.equal(job.model_id, 'host-model')
  assert.equal(job.meta.file_size, 100)
  assert.equal(job.meta.workflow, 'paper_extraction')
  assert.equal(job.meta.api_keys, undefined)
  assert.equal(JSON.stringify(job).includes('secret'), false)
})

test('upload history prefers server names then original PAPER metadata over UUID storage names', () => {
  const job = { job_id: 'upload', file_path: '/app/data/uploads/12345678-1111-2222-3333-444455556666.pdf', meta: { original_filename: 'Original agreement.pdf', api_keys: { credential: 'private' } } }
  assert.equal(normalizeHistoryJob({ ...job, filename: 'Server name.pdf' }).filename, 'Server name.pdf')
  assert.equal(normalizeHistoryJob(job).filename, 'Original agreement.pdf')
  assert.equal(normalizeHistoryJob({ ...job, meta: {} }).filename, '12345678-1111-2222-3333-444455556666.pdf')
  assert.equal(normalizeHistoryJob({ job_id: 'upload', meta: {} }).filename, 'upload')
  assert.equal(normalizeHistoryJob(job).meta.api_keys, undefined)
  assert.equal(JSON.stringify(normalizeHistoryJob(job)).includes('private'), false)
})

test('blocked legacy browser storage cannot prevent server-backed history from opening', () => {
  assert.doesNotThrow(() => discardLegacyJobCache({ removeItem() { throw new Error('Storage blocked') } }))
  const removed = []
  discardLegacyJobCache({ removeItem(key) { removed.push(key) } })
  assert.deepEqual(removed, ['unisensory_jobs'])
})

test('a history refresh retains uploads accepted during the request and never revives deleted rows', () => {
  const before = [{ job_id: 'new', status: 'pending' }, { job_id: 'existing', status: 'processing' }]
  const server = [{ job_id: 'deleted' }, { job_id: 'existing', status: 'completed' }]
  const merged = reconcileHistorySnapshot(before, server, new Set(['new']), new Set(['deleted']))
  assert.deepEqual(merged, [{ job_id: 'new', status: 'pending' }, { job_id: 'existing', status: 'completed' }])
  assert.equal(reconcileHistorySnapshot(before, [...server, before[0]], new Set(['new']), new Set(['deleted'])).filter(job => job.job_id === 'new').length, 1)
})
