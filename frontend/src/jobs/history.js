import { modelIds } from './presentation.js'

/** A history boundary changes for every authenticated account, tenant, or API host. */
export function jobScope(user, backendUrl = '') {
  return user?.user_id && user?.tenant_id ? JSON.stringify([user.tenant_id, user.user_id, backendUrl]) : null
}

export function jobsForScope(state, scope) {
  return scope && state.scope === scope ? state.jobs : []
}

/** Reconcile an asynchronous server snapshot without losing concurrent user actions. */
export function reconcileHistorySnapshot(previous, records, addedDuringRequest, removed) {
  const server = new Map(records.filter(job => !removed.has(job.job_id)).map(job => [job.job_id, job]))
  const additions = previous.filter(job => addedDuringRequest.has(job.job_id) && !server.has(job.job_id) && !removed.has(job.job_id))
  return [...additions, ...server.values()]
}

/** Keep only display metadata; credentials never enter the shared UI job cache. */
export function normalizeHistoryJob(job) {
  const basename = job.file_path?.split(/[/\\]/).pop()?.replace(/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}_/i, '')
  const meta = Object.fromEntries(['model_id', 'model_ids', 'file_size', 'error', 'workflow', 'schema_name', 'content_mode', 'retry_of', 'start_page', 'end_page', 'page_count', 'warning_count', 'extraction_status'].filter(key => job.meta?.[key] !== undefined).map(key => [key, job.meta[key]]))
  const ids = modelIds(job)
  return {
    job_id: job.job_id, status: job.status?.toLowerCase(), filename: job.filename || job.meta?.original_filename || basename || job.job_id,
    model_id: ids.length === 1 ? ids[0] : null,
    model_ids: ids,
    model_usage_recorded: job.model_usage_recorded ?? (job.meta?.model_ids !== undefined),
    created_at: job.created_at, updated_at: job.updated_at,
    documents: job.documents || [], fileSize: job.fileSize ?? meta.file_size,
    meta,
  }
}

/** Older session-only document caches are discarded, including when storage is disabled. */
export function discardLegacyJobCache(storage) {
  try { (storage || globalThis.sessionStorage)?.removeItem('unisensory_jobs') } catch { /* Server history remains authoritative. */ }
}
