import { sourceForDraft } from './sourceReview.js'

const object = value => value !== null && typeof value === 'object' && !Array.isArray(value)
const text = value => typeof value === 'string' && value.trim() ? value : null
const ROLES = ['landlord', 'tenant', 'other', 'unknown']
const BASE = '/extensions/party_roles/parties'

/** Project explicit source role candidates without inferring principals, roles or IDs. */
export function partyRoleReview(terms = {}) {
  const extensions = object(terms?.extensions) ? terms.extensions : {}
  const present = Object.hasOwn(extensions, 'party_roles')
  const metadata = extensions.party_roles
  const supported = object(metadata) && metadata.version === '1' && Array.isArray(metadata.parties)
  const parties = supported ? metadata.parties.flatMap((party, index) => object(party) ? [{
    index, path: `${BASE}/${index}`, name: text(party.name),
    role: ROLES.includes(party.role) ? party.role : 'unknown', sourceRole: text(party.source_role),
    representatives: Array.isArray(party.representatives) ? party.representatives.flatMap((representative, representativeIndex) => object(representative) ? [{
      index: representativeIndex, path: `${BASE}/${index}/representatives/${representativeIndex}`,
      name: text(representative.name), represents: text(representative.represents), capacity: text(representative.capacity),
    }] : []) : [],
  }] : []) : []
  return {
    present, supported, parties, supplier: text(terms?.vendor_name),
    landlords: parties.filter(party => party.role === 'landlord' && party.name).map(party => party.name),
    tenants: parties.filter(party => party.role === 'tenant' && party.name).map(party => party.name),
  }
}

/** Name exactly the source candidates a human must review before publication. */
export function partyRoleAcknowledgement(terms) {
  const review = partyRoleReview(terms)
  return `I verified the legal landlord: ${review.landlords.join('; ') || 'not established'}; tenant: ${review.tenants.join('; ') || 'not established'}; and the complete representation chains against the original PDF. The rent supplier must be the landlord. This acknowledgement does not resolve missing or conflicting evidence.`
}

function existingParty(terms, index) {
  const metadata = terms?.extensions?.party_roles
  if (!object(metadata) || !Array.isArray(metadata.parties) || !Number.isInteger(index) || index < 0 || !object(metadata.parties[index])) throw new Error('This source party is unavailable for editing.')
  return metadata
}

/** Correct one role candidate while leaving supplier values and other extensions independent. */
export function changePartyRole(terms, index, field, value) {
  if (!['name', 'role', 'source_role'].includes(field) || (typeof value !== 'string' && !(value === null && field !== 'role'))) throw new Error('This party field is not editable.')
  const metadata = existingParty(terms, index)
  return { ...terms, extensions: { ...terms.extensions, party_roles: { ...metadata, parties: metadata.parties.map((party, position) => position === index ? { ...party, [field]: value } : party) } } }
}

/** Correct a representation step without renaming its principal or manufacturing evidence. */
export function changePartyRepresentative(terms, index, representativeIndex, field, value) {
  if (!['name', 'represents', 'capacity'].includes(field) || (typeof value !== 'string' && !(value === null && field !== 'name'))) throw new Error('This representative field is not editable.')
  const metadata = existingParty(terms, index)
  const representatives = metadata.parties[index].representatives
  if (!Array.isArray(representatives) || !Number.isInteger(representativeIndex) || representativeIndex < 0 || !object(representatives[representativeIndex])) throw new Error('This source representative is unavailable for editing.')
  return { ...terms, extensions: { ...terms.extensions, party_roles: { ...metadata, parties: metadata.parties.map((party, position) => position === index ? { ...party, representatives: representatives.map((representative, representativePosition) => representativePosition === representativeIndex ? { ...representative, [field]: value } : representative) } : party) } } }
}

/** Select one exact original; multiple source documents require an explicit choice. */
export function agreementSourceOptions(ids = [], selectedId = '') {
  const sources = [...new Set(Array.isArray(ids) ? ids.filter(id => typeof id === 'string' && id.trim()) : [])]
  return { ids: sources, documentId: sources.length === 1 ? sources[0] : sources.includes(selectedId) ? selectedId : '', needsSelection: sources.length > 1 }
}

/** Resolve a saved agreement's exact original through the host's scoped API boundary. */
export async function loadAgreementSource(api, documentId) {
  if (typeof documentId !== 'string' || !documentId.trim()) throw new Error('Choose a source document before loading its original.')
  const record = await api.extractionByDocument(documentId)
  if (!sourceForDraft(record, [documentId])) throw new Error('Stored agreement extraction does not match this source document.')
  return record
}

/** Ignore stale host, agreement-version and source responses before rendering PDF shortcuts. */
export function currentAgreementSource(resource, api, key, documentId) {
  return resource?.api === api && resource.key === key && resource.documentId === documentId
    ? sourceForDraft(resource.record, [documentId]) : null
}
