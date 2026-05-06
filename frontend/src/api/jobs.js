import { apiFetch } from './client'

/**
 * Normalize a backend job object to a consistent frontend shape.
 * - Lowercases status (backend returns uppercase enum values)
 * - Hoists model_id from meta to root level
 */
function normalizeJob(job) {
  return {
    ...job,
    status: job.status?.toLowerCase(),
    model_id: job.model_id || job.meta?.model_id || null,
  }
}

/**
 * Upload a document for processing.
 * @param {File} file
 * @param {string} modelId
 * @param {string} baseUrl
 * @returns {{ job_id: string, status: string, message: string }}
 */
export async function uploadDocument(file, modelId = 'qwen3-vl-30b', baseUrl = '', apiKeys = null, startPage = null, endPage = null) {
  const form = new FormData()
  form.append('file', file)
  form.append('model_id', modelId)
  
  if (apiKeys) {
    // Only pass keys that have values to avoid empty overrides
    const validKeys = Object.fromEntries(
      Object.entries(apiKeys).filter(([_, v]) => v && v.trim() !== '')
    )
    if (Object.keys(validKeys).length > 0) {
      form.append('api_keys', JSON.stringify(validKeys))
    }
  }

  if (startPage) {
    form.append('start_page', startPage)
  }
  if (endPage) {
    form.append('end_page', endPage)
  }

  return apiFetch('/v1/process_document', {
    method: 'POST',
    body: form,
    baseUrl,
    timeout: 60000,
  })
}

/**
 * Get job status and results.
 * @param {string} jobId
 * @param {string} baseUrl
 */
export async function getJob(jobId, baseUrl = '') {
  const data = await apiFetch(`/v1/jobs/${jobId}`, { baseUrl })
  return normalizeJob(data)
}

/**
 * List all jobs from the backend.
 * @param {string} baseUrl
 * @param {number} limit
 * @param {number} offset
 */
export async function listJobs(baseUrl = '', limit = 50, offset = 0) {
  const data = await apiFetch(`/v1/jobs?limit=${limit}&offset=${offset}`, { baseUrl })
  return Array.isArray(data) ? data.map(normalizeJob) : data
}

/**
 * Delete a job and its documents.
 * @param {string} jobId
 * @param {string} baseUrl
 */
export async function deleteJob(jobId, baseUrl = '') {
  return apiFetch(`/v1/jobs/${jobId}`, { method: 'DELETE', baseUrl })
}

/**
 * Retry a failed job.
 * @param {string} jobId
 * @param {string} baseUrl
 */
export async function retryJob(jobId, baseUrl = '') {
  return apiFetch(`/v1/jobs/${jobId}/retry`, { method: 'POST', baseUrl })
}
