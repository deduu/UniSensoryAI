/** Resolve recorded model identities without substituting today's upload selection. */
export function modelIds(record) {
  const saved = record?.model_ids ?? record?.meta?.model_ids
  const ids = Array.isArray(saved) ? saved : []
  const unique = [...new Set(ids.filter(value => typeof value === 'string').map(value => value.trim()).filter(Boolean))]
  if (unique.length) return unique
  if (record?.model_usage_recorded || record?.meta?.model_ids !== undefined) return []
  const legacy = record?.model_id || record?.meta?.model_id
  return typeof legacy === 'string' && legacy.trim() ? [legacy.trim()] : []
}

/** Use the same honest model label in history, document lists, and review panes. */
export function modelLabel(record) {
  const ids = modelIds(record)
  if (ids.length) return ids.join(', ')
  const status = (record?.job_status || record?.status || '').toLowerCase()
  const isPaper = record?.meta?.workflow === 'paper_extraction' || record?.schema_name
  if (isPaper && ['pending', 'queued', 'processing'].includes(status)) return 'Server configured'
  return record?.model_usage_recorded ? 'No model recorded' : 'Not recorded'
}

export function modelDescription(record) {
  const ids = modelIds(record)
  if (ids.length) return `Recorded extraction models: ${ids.join(', ')}`
  if (modelLabel(record) === 'Server configured') return 'The server selects extraction models. Their identities appear when results are saved.'
  if (record?.model_usage_recorded) return 'No model identity was retained in a successful extraction result.'
  return 'Model identity was not saved for this extraction. The current upload selection does not identify past runs.'
}

/** Project safe job metadata once so every document entry point has the same details. */
export function documentForJob(job, document) {
  const ownModel = document.model_id || document.model_ids?.length || document.meta?.model_id || document.meta?.model_ids !== undefined
  const source = ownModel ? document : job
  const ids = modelIds(source)
  return {
    ...document,
    job_id: job.job_id,
    job_status: job.status?.toLowerCase(),
    model_id: ids.length === 1 ? ids[0] : null,
    model_ids: ids,
    model_usage_recorded: source.model_usage_recorded ?? (source.meta?.model_ids !== undefined),
    created_at: document.created_at ?? job.created_at,
    updated_at: document.updated_at ?? job.updated_at,
    file_size: document.file_size ?? job.meta?.file_size ?? job.fileSize,
    page_count: document.page_count ?? job.meta?.page_count,
    meta: { ...job.meta, ...document.meta },
  }
}

/** Match a refreshed document by identity, including jobs producing several documents. */
export function findJobDocument(job, documentId) {
  const document = documentId == null ? null : job.documents?.find(item => item.id === documentId)
  return document ? documentForJob(job, document) : null
}
