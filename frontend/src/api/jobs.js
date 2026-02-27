import { apiFetch } from './client'

/**
 * Upload a document for processing.
 * @param {File} file
 * @param {string} modelId
 * @param {string} baseUrl
 * @returns {{ job_id: string, status: string, message: string }}
 */
export async function uploadDocument(file, modelId = 'qwen3-vl-30b', baseUrl = '') {
  const form = new FormData()
  form.append('file', file)
  form.append('model_id', modelId)

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
  return apiFetch(`/v1/jobs/${jobId}`, { baseUrl })
}

/**
 * List all jobs from the backend.
 * @param {string} baseUrl
 * @param {number} limit
 * @param {number} offset
 */
export async function listJobs(baseUrl = '', limit = 50, offset = 0) {
  return apiFetch(`/v1/jobs?limit=${limit}&offset=${offset}`, { baseUrl })
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
