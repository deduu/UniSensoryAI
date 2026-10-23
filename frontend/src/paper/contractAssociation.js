const IDENTITY = ['vendor_id', 'store_id', 'contract_number']
const identityMatches = (left, right) => IDENTITY.every(key => left?.[key] === right?.[key])
const canonical = value => Array.isArray(value) ? value.map(canonical) : value && typeof value === 'object' ? Object.fromEntries(Object.keys(value).sort().map(key => [key, canonical(value[key])])) : value

/** Detect source or reviewed-coverage changes without persisting inferred source values. */
export function associationFingerprint(pkg) {
  return JSON.stringify(canonical({ invoice: pkg?.invoice, review_context: pkg?.review_context ?? null }))
}

/** A source edit requires another explicit association decision; other attachments stay independent. */
export function invalidateAssociation(previous, next) {
  return previous?.association && (associationFingerprint(previous) !== associationFingerprint(next) || !identityMatches(previous.identity, next.identity)) ? { ...next, association: null } : next
}

/** Restrict selection to a complete, eligible candidate and the locked identity of a revised case. */
export function candidateAllowed(candidate, lockedIdentity = null) {
  return Boolean(candidate?.agreement_id && Number.isInteger(candidate.version_number) && candidate.version_number > 0
    && candidate.eligible === true && candidate.coverage !== 'conflicting'
    && IDENTITY.every(key => typeof candidate.identity?.[key] === 'string' && candidate.identity[key].trim())
    && (!lockedIdentity || identityMatches(candidate.identity, lockedIdentity)))
}

/** Assign reviewed master IDs while retaining every extracted field and source citation unchanged. */
export function confirmAssociation(pkg, candidate, reason, lockedIdentity = null) {
  if (!candidateAllowed(candidate, lockedIdentity)) throw new Error('Choose an eligible contract candidate for this case identity.')
  if (typeof reason !== 'string' || !reason.trim()) throw new Error('Provide a reason for confirming this contract association.')
  return { ...pkg, identity: { ...candidate.identity }, association: { agreement_id: candidate.agreement_id, version_number: candidate.version_number, reason: reason.trim() } }
}

/** An exact approved version, rather than the latest agreement, supplies candidate source material. */
export function candidateAuthority(candidate, agreement) {
  return candidate && agreement?.approval && candidate.agreement_id === agreement.agreement_id && candidate.version_number === agreement.version_number && identityMatches(candidate.identity, agreement.identity) ? agreement : null
}

/** Only explicit JSON field paths can create evidence shortcuts. */
export function associationSignalPaths(signal, side) {
  return [...new Set((signal?.[`${side}_paths`] || []).filter(path => typeof path === 'string' && path.startsWith('/')))]
}

/** Supporting wording differences need human review; exact identifiers retain the conflict label. */
export function associationSignalResult(signal) {
  if (signal.status === 'matched') return { label: 'Matching reference', tone: 'reported' }
  if (signal.status === 'conflicting') {
    if (signal.strength === 'exact') return { label: 'Conflicting reference', tone: 'blocking' }
    return { label: signal.strength === 'supporting' ? 'Different wording · review' : 'Coverage needs review', tone: 'review' }
  }
  return { label: signal.status === 'unverified' ? 'Unverified reference' : 'Missing reference', tone: 'unknown' }
}

/** Read the exact approved version and canonical extraction records through an injected host API. */
export async function loadAssociationResources(api, candidate, pkg) {
  let agreement = null
  let error = ''
  try {
    agreement = candidateAuthority(candidate, await api.agreementVersion(candidate.agreement_id, candidate.version_number))
    if (!agreement) error = 'The returned contract is not the selected approved version. Refresh candidates before confirming.'
  } catch { error = 'The selected approved contract version could not be loaded. Retry before confirming.' }
  const ids = [...new Set([pkg.invoice.source_document_id, ...(agreement?.draft?.source_document_ids || [])].filter(Boolean))]
  const sources = await Promise.all(ids.map(async documentId => {
    try {
      const record = await api.extractionByDocument(documentId)
      if (record?.result?.document?.document_id !== documentId) throw new Error('Source identity mismatch')
      return { documentId, record, error: '' }
    } catch { return { documentId, record: null, error: 'Stored PDF or extraction is unavailable. Inspect the original independently before confirming.' } }
  }))
  return { agreement, error, sources }
}
