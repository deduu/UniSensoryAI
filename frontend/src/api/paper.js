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

function workspacePage(options = {}) {
  const { q, status, workflow_status, agreement_id, association_kind, job_id, archived, limit = 20, offset = 0, ...requestOptions } = options
  const filters = { q, status, workflow_status, agreement_id, association_kind, job_id, archived, limit, offset }
  const query = new URLSearchParams(Object.entries(filters).filter(([, value]) => value !== undefined && value !== null && value !== ''))
  return { query: `?${query}`, requestOptions }
}

function draftPage(options = {}) {
  const { q, role, status, limit = 20, offset = 0, ...requestOptions } = options
  const filters = { q, role, status, limit, offset }
  return { query: `?${new URLSearchParams(Object.entries(filters).filter(([, value]) => value !== undefined && value !== null && value !== ''))}`, requestOptions }
}

/** Bind every PAPER boundary to one host, optionally refreshing shared upload history. */
export function createPaperApi(baseUrl, { onExtractionQueued, onExtractionChanged } = {}) {
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
  listExtractions(options = {}) {
    const { archived, ...rest } = options
    const { query, requestOptions } = page(rest)
    return request(`/extractions${query}${archived === undefined ? '' : `&archived=${archived === true}`}`, 'GET', undefined, requestOptions)
  },
  async archiveExtractions(jobIds, archived = true, options) {
    const result = await request('/extractions/archive', 'POST', { job_ids: jobIds, archived }, options)
    try { await onExtractionChanged?.(result) } catch { /* The archive succeeded; shared history can refresh independently. */ }
    return result
  },
  getExtraction: (id, options) => request(`/extractions/${encoded(id)}`, 'GET', undefined, options),
  extractionByDocument: (id, options) => request(`/extractions/by-document/${encoded(id)}`, 'GET', undefined, options),
  retryExtraction: (id, options) => queued(`/extractions/${encoded(id)}/retry`, options),
  extractionFileUrl: (id, overrideBase = API_BASE) => `${boundBase ?? overrideBase.replace(/\/+$/, '')}${ROOT}/extractions/${encoded(id)}/file`,
  extractionPageUrl(id, pageNumber, overrideBase = API_BASE) {
    if (!Number.isInteger(pageNumber) || pageNumber < 1 || pageNumber > 500) throw new RangeError('PDF page must be between 1 and 500.')
    return `${boundBase ?? overrideBase.replace(/\/+$/, '')}${ROOT}/extractions/${encoded(id)}/pages/${pageNumber}`
  },
  getSchemas: options => request('/schemas', 'GET', undefined, options),
  getSchema: (name, options) => request(`/schemas/${encoded(name)}`, 'GET', undefined, options),
  reviewContext: options => request('/review-context', 'GET', undefined, options),
  fieldRequirements: options => request('/field-requirements', 'GET', undefined, options),
  saveFieldRequirements: (payload, options) => request('/field-requirements', 'PUT', payload, options),
  listDocumentDrafts(options) {
    const { query, requestOptions } = draftPage(options)
    return request(`/document-drafts${query}`, 'GET', undefined, requestOptions)
  },
  createDocumentDraft: (payload, options) => request('/document-drafts', 'POST', payload, options),
  reviseDocumentDraft: (id, payload, options) => request(`/document-drafts/${encoded(id)}/versions`, 'POST', payload, options),
  documentDraftVersion: (id, version, options) => request(`/document-drafts/${encoded(id)}/versions/${encoded(version)}`, 'GET', undefined, options),
  documentDraftVersions(id, options) {
    const { query, requestOptions } = page(options)
    return request(`/document-drafts/${encoded(id)}/versions${query}`, 'GET', undefined, requestOptions)
  },
  caseReadiness: (payload, options) => request('/cases/preparation/readiness', 'POST', payload, options),
  reconcileDraftSelection: (payload, options) => request('/cases/from-drafts', 'POST', payload, options),
  workspaceCases(options) {
    const { query, requestOptions } = workspacePage(options)
    return request(`/workspace/cases${query}`, 'GET', undefined, requestOptions)
  },
  workspaceContracts(options) {
    const { query, requestOptions } = workspacePage(options)
    return request(`/workspace/contracts${query}`, 'GET', undefined, requestOptions)
  },
  workspaceDocuments(options) {
    const { query, requestOptions } = workspacePage(options)
    return request(`/workspace/documents${query}`, 'GET', undefined, requestOptions)
  },
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
  associationCandidates: (payload, options) => request('/cases/association/candidates', 'POST', payload, options),
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
