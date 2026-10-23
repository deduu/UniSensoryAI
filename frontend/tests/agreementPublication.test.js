import test from 'node:test'
import assert from 'node:assert/strict'
import { missingPublicationFields } from '../src/paper/agreementPublication.js'

test('publication checks assigned identity without filling missing extracted identifiers', () => {
  const version = { identity: { vendor_id: 'local-vendor', store_id: 'local-store', contract_number: '65' }, draft: { terms: { vendor_id: null, store_id: null, contract_number: null, rent_type: 'fixed', fixed_rent: '0', vendor_name: 'Owner' } } }
  const context = { agreement_required_fields: ['vendor_id', 'store_id', 'contract_number', 'vendor_name'], agreement_required_fields_by_rent_type: { fixed: ['fixed_rent'] } }
  const before = structuredClone(version)
  assert.deepEqual(missingPublicationFields(version, context), [])
  assert.deepEqual(version, before)
  assert.deepEqual(missingPublicationFields({ ...version, identity: { ...version.identity, store_id: '' } }, context), ['store_id'])
  assert.deepEqual(missingPublicationFields({ ...version, draft: { terms: { ...version.draft.terms, vendor_name: null, fixed_rent: null } } }, context), ['vendor_name', 'fixed_rent'])
})

test('source fields cannot substitute an absent assigned identity and requirements deduplicate', () => {
  const version = { draft: { terms: { store_id: 'printed-reference' } } }
  assert.deepEqual(missingPublicationFields(version, { agreement_required_fields: ['store_id', 'store_id'] }), ['store_id'])
  assert.deepEqual(missingPublicationFields(null, null), [])
})
