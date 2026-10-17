import { API_BASE, apiFetch } from './client.js'

const ROOT = '/v1/paper'
const encoded = value => encodeURIComponent(String(value))

function rawRequest(path, method = 'GET', payload, options = {}) {
  const { baseUrl, ...rest } = options
  return apiFetch(`${ROOT}${path}`, {
    ...(baseUrl !== undefined ? { baseUrl } : {}),
    ...rest,
    method,
    ...(payload === undefined ? {} : {
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  })
}

function page(options = {}) {
  const { limit = 25, offset = 0, ...requestOptions } = options
  return { query: `?${new URLSearchParams({ limit, offset })}`, requestOptions }
}

/** Bind every PAPER boundary to one host, optionally refreshing shared upload history. */
export function createPaperApi(baseUrl, { onExtractionQueued } = {}) {
  const boundBase = baseUrl?.replace(/\/+$/, '')
  const request = (path, method, payload, options = {}) => rawRequest(path, method, payload, {
    ...options, ...(boundBase === undefined ? {} : { baseUrl: boundBase }),
  })
  const queued = async (path, options) => {
    const result = await request(path, 'POST', undefined, options)
    try { await onExtractionQueued?.(result) } catch { /* Accepted uploads remain successful; history displays its own refresh error. */ }
    return result
  }
  return {
  uploadExtraction(file, schemaName, contentMode = 'text', options) {
    const body = new FormData()
    body.append('file', file)
    body.append('schema_name', schemaName)
    body.append('content_mode', contentMode)
    return queued('/extractions', { ...options, body, timeout: 60000 })
  },
  listExtractions(options) {
    const { query, requestOptions } = page(options)
    return request(`/extractions${query}`, 'GET', undefined, requestOptions)
  },
  getExtraction: (id, options) => request(`/extractions/${encoded(id)}`, 'GET', undefined, options),
  retryExtraction: (id, options) => queued(`/extractions/${encoded(id)}/retry`, options),
  extractionFileUrl: (id, overrideBase = API_BASE) => `${boundBase ?? overrideBase.replace(/\/+$/, '')}${ROOT}/extractions/${encoded(id)}/file`,
  extractionPageUrl(id, pageNumber, overrideBase = API_BASE) {
    if (!Number.isInteger(pageNumber) || pageNumber < 1 || pageNumber > 500) throw new RangeError('PDF page must be between 1 and 500.')
    return `${boundBase ?? overrideBase.replace(/\/+$/, '')}${ROOT}/extractions/${encoded(id)}/pages/${pageNumber}`
  },
  getSchemas: options => request('/schemas', 'GET', undefined, options),
  getSchema: (name, options) => request(`/schemas/${encoded(name)}`, 'GET', undefined, options),
  reviewContext: options => request('/review-context', 'GET', undefined, options),
  listAgreements(options) {
    const { query, requestOptions } = page(options)
    return request(`/agreements${query}`, 'GET', undefined, requestOptions)
  },
  createAgreement: (payload, options) => request('/agreements', 'POST', payload, options),
  reviseAgreement: (id, payload, options) => request(`/agreements/${encoded(id)}/versions`, 'POST', payload, options),
  agreementVersions(id, options) {
    const { query, requestOptions } = page(options)
    return request(`/agreements/${encoded(id)}/versions${query}`, 'GET', undefined, requestOptions)
  },
  agreementVersion: (id, version, options) => request(`/agreements/${encoded(id)}/versions/${encoded(version)}`, 'GET', undefined, options),
  approveAgreement: (id, version, decision, options) => request(`/agreements/${encoded(id)}/versions/${encoded(version)}/approval`, 'POST', decision, options),
  approvedAgreement(identity, asOf, options) {
    const query = new URLSearchParams({ ...identity, as_of: asOf })
    return request(`/agreements/approved?${query}`, 'GET', undefined, options)
  },
  listCases(options) {
    const { query, requestOptions } = page(options)
    return request(`/cases${query}`, 'GET', undefined, requestOptions)
  },
  createCase: (payload, options) => request('/cases', 'POST', payload, options),
  reviseCase: (id, payload, options) => request(`/cases/${encoded(id)}/versions`, 'POST', payload, options),
  caseVersions(id, options) {
    const { query, requestOptions } = page(options)
    return request(`/cases/${encoded(id)}/versions${query}`, 'GET', undefined, requestOptions)
  },
  caseVersion: (id, version, options) => request(`/cases/${encoded(id)}/versions/${encoded(version)}`, 'GET', undefined, options),
  decideCase: (id, version, decision, options) => request(`/cases/${encoded(id)}/versions/${encoded(version)}/decision`, 'POST', decision, options),
  }
}

export const paperApi = createPaperApi()
