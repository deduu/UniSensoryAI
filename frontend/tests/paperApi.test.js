import test from 'node:test'
import assert from 'node:assert/strict'
import { createPaperApi, paperApi } from '../src/api/paper.js'

test('PAPER API uses encoded identifiers, JSON requests, and configured base URL', async () => {
  const original = globalThis.fetch
  const requests = []
  globalThis.fetch = async (url, options) => {
    requests.push({url, options})
    return {ok: true, json: async () => ({saved: true})}
  }
  try {
    assert.deepEqual(await paperApi.createAgreement({identity: {vendor_id: 'A'}}, {baseUrl: 'http://local'}), {saved: true})
    await paperApi.approveAgreement('contract/a', 2, {reason: 'reviewed'})
    await paperApi.approvedAgreement({vendor_id: 'A & B', store_id: 'store', contract_number: 'C/1'}, '2026-06-01')
    await paperApi.listCases({limit: 10, offset: 20})
    await paperApi.decideCase('case/a', 3, {action: 'reject', reason: 'Incorrect'})
    assert.equal(requests[0].url, 'http://local/v1/paper/agreements')
    assert.equal(requests[0].options.credentials, 'include')
    assert.equal(requests[0].options.method, 'POST')
    assert.deepEqual(JSON.parse(requests[0].options.body), {identity: {vendor_id: 'A'}})
    assert.equal(requests[1].url, '/v1/paper/agreements/contract%2Fa/versions/2/approval')
    const query = new URL(requests[2].url, 'http://local').searchParams
    assert.equal(query.get('vendor_id'), 'A & B')
    assert.equal(query.get('as_of'), '2026-06-01')
    assert.equal(requests[3].url, '/v1/paper/cases?limit=10&offset=20')
    assert.equal(requests[4].url, '/v1/paper/cases/case%2Fa/versions/3/decision')
  } finally { globalThis.fetch = original }
})

test('PAPER catalog, history and review-context reads remain read-only', async () => {
  const original = globalThis.fetch
  const requests = []
  globalThis.fetch = async (url, options) => {
    requests.push({url, options})
    return {ok: true, json: async () => []}
  }
  try {
    await paperApi.getSchemas()
    await paperApi.getSchema('rent_invoice')
    await paperApi.reviewContext()
    await paperApi.listAgreements()
    await paperApi.agreementVersions('agreement')
    await paperApi.caseVersions('case')
    for (const request of requests) assert.equal(request.options.method, 'GET')
    assert.equal(requests[2].url, '/v1/paper/review-context')
  } finally { globalThis.fetch = original }
})

test('PAPER extraction submits multipart PDF without model credentials and reads persistent history', async () => {
  const original = globalThis.fetch
  const requests = []
  globalThis.fetch = async (url, options) => {
    requests.push({ url, options })
    return { ok: true, json: async () => ({ job_id: 'upload-1' }) }
  }
  try {
    await paperApi.uploadExtraction(new Blob(['%PDF-sample'], { type: 'application/pdf' }), 'rent_invoice', 'multimodal')
    await paperApi.listExtractions({ limit: 10, offset: 20 })
    await paperApi.getExtraction('job/a')
    await paperApi.retryExtraction('job/a')
    assert.equal(requests[0].url, '/v1/paper/extractions')
    assert.equal(requests[0].options.method, 'POST')
    assert.equal(requests[0].options.headers, undefined)
    assert.equal(requests[0].options.body.get('schema_name'), 'rent_invoice')
    assert.equal(requests[0].options.body.get('content_mode'), 'multimodal')
    assert.equal(requests[0].options.body.has('model_id'), false)
    assert.equal(requests[0].options.body.has('api_keys'), false)
    assert.equal(requests[1].url, '/v1/paper/extractions?limit=10&offset=20')
    assert.equal(requests[2].url, '/v1/paper/extractions/job%2Fa')
    assert.equal(requests[3].url, '/v1/paper/extractions/job%2Fa/retry')
    assert.equal(paperApi.extractionFileUrl('job/a'), '/v1/paper/extractions/job%2Fa/file')
    assert.equal(paperApi.extractionFileUrl('job/a', 'https://api.local/'), 'https://api.local/v1/paper/extractions/job%2Fa/file')
  } finally { globalThis.fetch = original }
})

test('a configured PAPER client binds every workflow and original source URL to one server', async () => {
  const original = globalThis.fetch
  const urls = []
  globalThis.fetch = async url => { urls.push(url); return { ok: true, json: async () => ({}) } }
  try {
    const api = createPaperApi('https://configured.local/')
    await api.getSchemas()
    await api.getSchema('rent_invoice')
    await api.reviewContext()
    await api.listAgreements()
    await api.createAgreement({})
    await api.reviseAgreement('agreement', {})
    await api.agreementVersions('agreement')
    await api.agreementVersion('agreement', 1)
    await api.approveAgreement('agreement', 1, {})
    await api.approvedAgreement({ vendor_id: 'vendor' }, '2026-10-15')
    await api.listCases()
    await api.createCase({})
    await api.reviseCase('case', {})
    await api.caseVersions('case')
    await api.caseVersion('case', 1)
    await api.decideCase('case', 1, {})
    await api.uploadExtraction(new Blob(['pdf']), 'rent_invoice')
    await api.listExtractions()
    await api.getExtraction('upload')
    await api.retryExtraction('upload')
    await api.getSchemas({ baseUrl: 'https://other.local' })
    assert.equal(urls.length, 21)
    assert.ok(urls.every(url => url.startsWith('https://configured.local/v1/paper/')))
    assert.equal(api.extractionFileUrl('job/a'), 'https://configured.local/v1/paper/extractions/job%2Fa/file')
    assert.equal(api.extractionFileUrl('job/a', 'https://other.local'), 'https://configured.local/v1/paper/extractions/job%2Fa/file')
    assert.equal(api.extractionPageUrl('job/a', 17), 'https://configured.local/v1/paper/extractions/job%2Fa/pages/17')
    assert.equal(paperApi.extractionPageUrl('job/a', 2, 'https://api.local/'), 'https://api.local/v1/paper/extractions/job%2Fa/pages/2')
    assert.throws(() => api.extractionPageUrl('job/a', 0), /page/i)
    assert.throws(() => api.extractionPageUrl('job/a', 1.5), /page/i)
  } finally { globalThis.fetch = original }
})

test('successful upload and retry refresh shared history, while rejected requests do not', async () => {
  const original = globalThis.fetch
  const refreshed = []
  let accepted = true
  globalThis.fetch = async () => ({ ok: accepted, status: accepted ? 202 : 400, json: async () => accepted ? { job_id: 'new-job' } : { detail: 'Invalid PDF' } })
  try {
    const api = createPaperApi('https://configured.local', { onExtractionQueued: async record => { refreshed.push(record.job_id) } })
    await api.uploadExtraction(new Blob(['pdf']), 'rent_agreement')
    await api.retryExtraction('old-job')
    assert.deepEqual(refreshed, ['new-job', 'new-job'])
    accepted = false
    await assert.rejects(() => api.uploadExtraction(new Blob(['bad']), 'rent_invoice'))
    await assert.rejects(() => api.retryExtraction('invalid'))
    assert.equal(refreshed.length, 2)
    accepted = true
    const offlineHistory = createPaperApi('https://configured.local', { onExtractionQueued: async () => { throw new Error('History temporarily unavailable') } })
    assert.equal((await offlineHistory.retryExtraction('old-job')).job_id, 'new-job')
  } finally { globalThis.fetch = original }
})
