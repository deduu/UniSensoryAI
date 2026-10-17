import test from 'node:test'
import assert from 'node:assert/strict'
import { getJob, listJobs } from '../src/api/jobs.js'
import { modelLabel } from '../src/jobs/presentation.js'

test('list and authenticated detail requests retain the same recorded model identities through the proxy', async () => {
  const previousFetch = globalThis.fetch
  const requests = []
  const record = { job_id: 'job', status: 'COMPLETED', meta: { model_ids: ['ocr', 'fields'], workflow: 'paper_extraction' } }
  globalThis.fetch = async (url, options) => {
    requests.push({ url, options })
    return { ok: true, json: async () => url.includes('?') ? [record] : record }
  }
  try {
    const listed = await listJobs('', 200, 0)
    const detail = await getJob('job', '')
    assert.equal(modelLabel(listed[0]), 'ocr, fields')
    assert.equal(modelLabel(detail), 'ocr, fields')
    assert.equal(detail.status, 'completed')
    assert.equal(detail.model_usage_recorded, true)
    assert.deepEqual(requests.map(({ url }) => url), ['/v1/jobs?limit=200&offset=0', '/v1/jobs/job'])
    assert.ok(requests.every(({ options }) => options.credentials === 'include' && options.signal instanceof AbortSignal))
  } finally {
    globalThis.fetch = previousFetch
  }
})
