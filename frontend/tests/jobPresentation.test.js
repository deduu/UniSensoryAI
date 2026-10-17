import test from 'node:test'
import assert from 'node:assert/strict'
import { documentForJob, findJobDocument, modelDescription, modelLabel } from '../src/jobs/presentation.js'
import { normalizeHistoryJob } from '../src/jobs/history.js'

test('model labels use saved identities, including multiple models, across job and document shapes', () => {
  assert.equal(modelLabel({ model_id: 'legacy-model' }), 'legacy-model')
  assert.equal(modelLabel({ meta: { model_id: 'saved-model' } }), 'saved-model')
  assert.equal(modelLabel({ model_id: 'requested', meta: { model_ids: ['ocr-model', 'fields-model', 'ocr-model'] } }), 'ocr-model, fields-model')
  assert.equal(modelLabel({ model_ids: ['  model-a  ', '', null] }), 'model-a')
  assert.equal(modelLabel({ meta: { workflow: 'paper_extraction' }, status: 'COMPLETED' }), 'Not recorded')
  assert.match(modelDescription({}), /not saved/i)
  assert.equal(modelLabel({ meta: { workflow: 'paper_extraction' }, status: 'processing' }), 'Server configured')
  assert.equal(modelLabel({ schema_name: 'rent_agreement', status: 'pending' }), 'Server configured')
  assert.equal(modelLabel({ model_usage_recorded: true, model_ids: [] }), 'No model recorded')
  assert.equal(modelLabel({ model_usage_recorded: true, model_ids: [], model_id: 'requested-only' }), 'No model recorded')
})

test('history retains only safe model provenance and useful extraction display metadata', () => {
  const job = normalizeHistoryJob({ job_id: 'job', status: 'COMPLETED', meta: {
    model_ids: ['ocr-model', 'fields-model'], file_size: 0, start_page: 2, end_page: 3,
    page_count: 2, extraction_status: 'partial', warning_count: 1, api_keys: { secret: 'private' },
  } })
  assert.deepEqual(job.model_ids, ['ocr-model', 'fields-model'])
  assert.equal(job.model_usage_recorded, true)
  assert.equal(job.meta.start_page, 2)
  assert.equal(job.meta.end_page, 3)
  assert.equal(job.meta.page_count, 2)
  assert.equal(job.meta.warning_count, 1)
  assert.equal(job.fileSize, 0)
  assert.equal(JSON.stringify(job).includes('private'), false)
  assert.equal(modelLabel(normalizeHistoryJob({ job_id: 'old', meta: {} })), 'Not recorded')
})

test('document projection preserves document identity and carries safe job metadata consistently', () => {
  const job = normalizeHistoryJob({ job_id: 'job', status: 'COMPLETED', created_at: 'created', updated_at: 'updated', fileSize: 120,
    meta: { workflow: 'paper_extraction', model_ids: ['ocr', 'fields'], start_page: 2, page_count: 4 },
  })
  const input = { id: 'doc', filename: 'source.pdf', content_text: 'text' }
  const projected = documentForJob(job, input)
  assert.equal(projected.job_id, 'job')
  assert.equal(projected.job_status, 'completed')
  assert.equal(projected.updated_at, 'updated')
  assert.equal(projected.file_size, 120)
  assert.equal(projected.page_count, 4)
  assert.equal(projected.meta.start_page, 2)
  assert.equal(modelLabel(projected), 'ocr, fields')
  assert.equal(modelLabel(documentForJob(job, { ...input, model_id: 'document-model' })), 'document-model')
  assert.equal(modelLabel(documentForJob(job, { ...input, meta: { model_ids: ['document-model'] } })), 'document-model')
  assert.deepEqual(input, { id: 'doc', filename: 'source.pdf', content_text: 'text' })
})

test('detail refresh selects the exact document and never substitutes the first document', () => {
  const job = { job_id: 'job', status: 'completed', model_id: 'saved-model', documents: [
    { id: 'first', content_text: 'Wrong document' }, { id: 'second', content_text: 'Selected document' },
  ] }
  assert.equal(findJobDocument(job, 'second').content_text, 'Selected document')
  assert.equal(findJobDocument(job, 'second').model_id, 'saved-model')
  assert.equal(findJobDocument(job, 'missing'), null)
  assert.equal(findJobDocument(job, undefined), null)
})
