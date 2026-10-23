import test from 'node:test'
import assert from 'node:assert/strict'
import {
  agreementSourceOptions, changePartyRepresentative, changePartyRole, currentAgreementSource,
  loadAgreementSource, partyRoleAcknowledgement, partyRoleReview,
} from '../src/paper/agreementPartyReview.js'

const terms = {
  vendor_name: 'Owner Principal', vendor_id: null, extensions: {
    fixed_rent_basis: 'annual', party_roles: { version: '1', parties: [
      { name: 'Owner Principal', role: 'landlord', source_role: 'PIHAK PERTAMA', representatives: [{ name: 'Attorney', represents: 'Owner Principal', capacity: 'Power of attorney' }] },
      { name: 'Tenant Company', role: 'tenant', source_role: 'PIHAK KEDUA', representatives: [] },
    ] },
  },
}

test('party review preserves source names and explicit role paths without manufacturing IDs', () => {
  const before = structuredClone(terms)
  const review = partyRoleReview(terms)
  assert.equal(review.present, true)
  assert.equal(review.supported, true)
  assert.deepEqual(review.landlords, ['Owner Principal'])
  assert.deepEqual(review.tenants, ['Tenant Company'])
  assert.equal(review.supplier, 'Owner Principal')
  assert.equal(review.parties[0].path, '/extensions/party_roles/parties/0')
  assert.equal(review.parties[0].representatives[0].path, '/extensions/party_roles/parties/0/representatives/0')
  assert.equal('vendor_id' in review.parties[0], false)
  assert.deepEqual(terms, before)
})

test('legacy and malformed role metadata stay distinct and never become a verified party', () => {
  assert.equal(partyRoleReview({ vendor_name: 'Legacy name' }).present, false)
  for (const party_roles of [null, [], {}, { version: '2', parties: [] }, { version: '1', parties: 'wrong' }]) {
    const review = partyRoleReview({ extensions: { party_roles } })
    assert.equal(review.present, true)
    assert.equal(review.supported, false)
  }
  const partial = partyRoleReview({ extensions: { party_roles: { version: '1', parties: [null, { name: 'Ambiguous party', role: 'unknown', representatives: [] }] } } })
  assert.deepEqual(partial.landlords, [])
  assert.equal(partial.parties[0].index, 1)
  assert.equal(partial.parties[0].role, 'unknown')
})

test('explicit acknowledgement names both roles and does not infer missing or reversed roles', () => {
  assert.match(partyRoleAcknowledgement(terms), /landlord: Owner Principal/)
  assert.match(partyRoleAcknowledgement(terms), /tenant: Tenant Company/)
  const swapped = structuredClone(terms)
  swapped.extensions.party_roles.parties.reverse()
  assert.equal(partyRoleAcknowledgement(swapped), partyRoleAcknowledgement(terms))
  assert.match(partyRoleAcknowledgement({}), /landlord: not established/)
})

test('editing a principal or representative preserves other terms, source roles and supplier independently', () => {
  const before = structuredClone(terms)
  const renamed = changePartyRole(terms, 0, 'name', 'Reviewed Owner')
  assert.equal(renamed.extensions.party_roles.parties[0].name, 'Reviewed Owner')
  assert.equal(renamed.vendor_name, 'Owner Principal')
  assert.equal(renamed.extensions.fixed_rent_basis, 'annual')
  const represented = changePartyRepresentative(renamed, 0, 0, 'represents', 'Reviewed Owner')
  assert.equal(represented.extensions.party_roles.parties[0].representatives[0].represents, 'Reviewed Owner')
  assert.equal(represented.extensions.party_roles.parties[0].source_role, 'PIHAK PERTAMA')
  assert.deepEqual(terms, before)
  assert.throws(() => changePartyRole(terms, 0, 'vendor_id', 'Invented'), /editable/)
  assert.throws(() => changePartyRole(terms, 9, 'name', 'Absent'), /unavailable/)
  assert.throws(() => changePartyRepresentative(terms, 0, 9, 'name', 'Absent'), /unavailable/)
})

test('clearing optional party attributes preserves explicit unknown values', () => {
  assert.equal(changePartyRole(terms, 0, 'name', null).extensions.party_roles.parties[0].name, null)
  assert.equal(changePartyRepresentative(terms, 0, 0, 'capacity', null).extensions.party_roles.parties[0].representatives[0].capacity, null)
  assert.throws(() => changePartyRole(terms, 0, 'role', null), /editable/)
  assert.throws(() => changePartyRepresentative(terms, 0, 0, 'name', null), /editable/)
})

test('source selection deduplicates exact IDs, requires a choice for multiple originals and clears stale choices', () => {
  assert.deepEqual(agreementSourceOptions(['pdf-a', 'pdf-a'], ''), { ids: ['pdf-a'], documentId: 'pdf-a', needsSelection: false })
  assert.deepEqual(agreementSourceOptions(['pdf-a', 'pdf-b'], ''), { ids: ['pdf-a', 'pdf-b'], documentId: '', needsSelection: true })
  assert.equal(agreementSourceOptions(['pdf-a', 'pdf-b'], 'pdf-b').documentId, 'pdf-b')
  assert.equal(agreementSourceOptions(['pdf-c', 'pdf-d'], 'pdf-b').documentId, '')
  assert.deepEqual(agreementSourceOptions([]), { ids: [], documentId: '', needsSelection: false })
})

const source = { job_id: 'stored-job', result: { document: { document_id: 'pdf-a' } } }

test('saved agreement source lookup uses the exact ID and rejects unrelated or unavailable extraction', async () => {
  const calls = []
  const api = { extractionByDocument: async id => { calls.push(id); return source } }
  assert.equal(await loadAgreementSource(api, 'pdf-a'), source)
  assert.deepEqual(calls, ['pdf-a'])
  await assert.rejects(() => loadAgreementSource(api, 'pdf-b'), /does not match/)
  await assert.rejects(() => loadAgreementSource({ extractionByDocument: async () => ({ result: source.result }) }, 'pdf-a'), /does not match/)
  await assert.rejects(() => loadAgreementSource(api, ''), /source document/)
  const before = structuredClone(terms)
  await assert.rejects(() => loadAgreementSource({ extractionByDocument: async () => { throw new Error('Unavailable') } }, 'pdf-a'), /Unavailable/)
  assert.deepEqual(terms, before)
})

test('source presentation rejects stale document, version or host results immediately', () => {
  const api = {}
  const resource = { api, key: 'agreement-v1', documentId: 'pdf-a', record: source }
  assert.equal(currentAgreementSource(resource, api, 'agreement-v1', 'pdf-a'), source)
  assert.equal(currentAgreementSource(resource, {}, 'agreement-v1', 'pdf-a'), null)
  assert.equal(currentAgreementSource(resource, api, 'agreement-v2', 'pdf-a'), null)
  assert.equal(currentAgreementSource(resource, api, 'agreement-v1', 'pdf-b'), null)
  assert.equal(currentAgreementSource({ ...resource, record: { ...source, result: { document: { document_id: 'foreign' } } } }, api, 'agreement-v1', 'pdf-a'), null)
})
