import { apiFetch } from './client'

export async function getPolicyReview(jobId, baseUrl = '') {
  return apiFetch(`/v1/jobs/${jobId}/policy-review`, {
    baseUrl,
    method: 'GET',
  })
}

export async function reviewPolicy(jobId, payload = {}, baseUrl = '') {
  return apiFetch(`/v1/jobs/${jobId}/policy-review`, {
    baseUrl,
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      include_database: true,
      include_web_search: true,
      include_trusted_sources: true,
      max_reference_documents: 10,
      focus: null,
      ...payload,
    }),
    timeout: 120000,
  })
}
