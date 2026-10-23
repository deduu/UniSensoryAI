/** Compare shared navigation counters without reinterpreting legacy unnumbered handoffs. */
export function isOlderWorkspaceIntent(requestId, otherRequestId) {
  return Number.isSafeInteger(requestId) && requestId >= 0
    && Number.isSafeInteger(otherRequestId) && otherRequestId >= 0
    && requestId < otherRequestId
}

/** Load a requested saved version without substituting the latest snapshot. */
export async function resolveWorkspaceSelection({ api, kind, id, versionNumber, limit = 100 }) {
  if (!['agreement', 'case'].includes(kind) || typeof id !== 'string' || !id.trim()) throw new Error('Invalid workspace selection.')
  const exact = versionNumber !== undefined && versionNumber !== null
  if (exact && (!Number.isInteger(versionNumber) || versionNumber < 1)) throw new Error('Invalid requested version.')
  if (!Number.isInteger(limit) || limit < 1 || limit > 100) throw new Error('Invalid selection history limit.')
  const idKey = kind === 'agreement' ? 'agreement_id' : 'case_id'
  const historyMethod = kind === 'agreement' ? 'agreementVersions' : 'caseVersions'
  const exactMethod = kind === 'agreement' ? 'agreementVersion' : 'caseVersion'
  const [history, requested] = await Promise.all([
    api[historyMethod](id, { limit, offset: 0 }),
    exact ? api[exactMethod](id, versionNumber) : null,
  ])
  if (!Array.isArray(history) || !history.length) throw new Error('No saved version history is available for the requested selection.')
  const valid = record => record?.[idKey] === id && Number.isInteger(record.version_number) && record.version_number > 0
  if (!history.every(valid)) throw new Error('The saved history does not match the requested selection.')
  const latest = Math.max(...history.map(record => record.version_number))
  const record = exact ? requested : history.find(item => item.version_number === latest)
  if (!valid(record) || (exact && record.version_number !== versionNumber)) throw new Error('The saved version does not match the requested selection.')
  if (history.some(item => item.tenant_id !== record.tenant_id)) throw new Error('The selected version and history do not share the same tenant.')
  return { record, history, latest }
}
