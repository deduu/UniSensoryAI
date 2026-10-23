import test from 'node:test'
import assert from 'node:assert/strict'
import {
  MATCH_DOCUMENT_TYPES, requirementFields, createRequirementDraft, updateFieldRequirement,
  updateRequirementCondition, parseConditionValue, serializeRequirements, requirementDraftChanged,
  serializeRequirementOverrides, requirementUsesHostDefault,
} from '../src/paper/fieldRequirements.js'

export const schemas = [
  { schema_id: 'paper.rent_invoice', json_schema: { properties: {
    invoice_number: { title: 'Invoice number', anyOf: [{ type: 'string' }, { type: 'null' }] },
    total: { anyOf: [{ type: 'string', pattern: '^-?(?:0|[1-9][0-9]*)(?:\\.[0-9]+)?$' }, { type: 'null' }] },
    approved: { type: 'boolean' }, count: { type: 'integer' }, ratio: { type: 'number' },
    category: { type: 'string', enum: ['rent', 'service'] }, extensions: { type: 'object' }, nested: { type: 'array' },
  } } },
  { schema_id: 'paper.tax_invoice', json_schema: { properties: { reference: { type: 'string' } } } },
  ...['utility_statement', 'supporting_document'].map(role => ({ schema_id: `paper.${role}`, json_schema: { properties: { description: { type: 'string' } } } })),
]
const policy = { revision: 2, policy_id: 'rent', policy_version: 3, can_edit: true, requirements: [
  { role: 'rent_invoice', field: 'invoice_number', requirement: 'required', reason: 'Identify the invoice.' },
] }

test('catalog contains the four matching document types and only supported scalar fields', () => {
  assert.equal(MATCH_DOCUMENT_TYPES.length, 4)
  assert.deepEqual(requirementFields(schemas, 'rent_invoice').map(field => field.name), ['invoice_number', 'total', 'approved', 'count', 'ratio', 'category'])
  assert.equal(requirementFields(schemas, 'rent_invoice')[0].label, 'Invoice number')
  assert.deepEqual(requirementFields([], 'rent_invoice'), [])
})

test('drafts preserve server requirements and changes across document-type switches', () => {
  const draft = createRequirementDraft(policy, schemas)
  const first = updateFieldRequirement(draft, 'rent_invoice', 'total', { requirement: 'required' }, schemas)
  const second = updateFieldRequirement(first, 'tax_invoice', 'reference', { requirement: 'conditional' }, schemas)
  assert.equal(second.find(row => row.field === 'total').requirement, 'required')
  assert.equal(second.find(row => row.field === 'reference').when.role, 'tax_invoice')
  assert.equal(draft.find(row => row.field === 'total').requirement, 'optional')
  assert.equal(policy.requirements.length, 1)
  assert.equal(requirementDraftChanged(draft, draft), false)
  assert.equal(requirementDraftChanged(draft, second), true)
})

test('presence conditions omit values and nonconditional requirements omit their predicate', () => {
  let rows = updateFieldRequirement(createRequirementDraft(policy, schemas), 'rent_invoice', 'total', { requirement: 'conditional' }, schemas)
  rows = updateRequirementCondition(rows, 'rent_invoice', 'total', { operator: 'equals' }, schemas)
  rows = updateRequirementCondition(rows, 'rent_invoice', 'total', { value: '9007199254740993.00100' }, schemas)
  assert.equal(serializeRequirements(rows, schemas).find(row => row.field === 'total').when.value, '9007199254740993.00100')
  rows = updateRequirementCondition(rows, 'rent_invoice', 'total', { operator: 'absent' }, schemas)
  assert.equal('value' in serializeRequirements(rows, schemas).find(row => row.field === 'total').when, false)
  rows = updateFieldRequirement(rows, 'rent_invoice', 'total', { requirement: 'optional' }, schemas)
  assert.equal('when' in serializeRequirements(rows, schemas).find(row => row.field === 'total'), false)
})

test('equals values retain schema types, exact decimal scale and false or zero', () => {
  const fields = requirementFields(schemas, 'rent_invoice')
  const byName = name => fields.find(field => field.name === name)
  assert.equal(parseConditionValue('0', byName('count')), 0)
  assert.equal(parseConditionValue('false', byName('approved')), false)
  assert.equal(parseConditionValue('0.25', byName('ratio')), 0.25)
  assert.equal(parseConditionValue('9007199254740993.000100', byName('total')), '9007199254740993.000100')
  assert.equal(parseConditionValue('service', byName('category')), 'service')
  assert.throws(() => parseConditionValue('', byName('count')), /number|integer/i)
  assert.throws(() => parseConditionValue('9007199254740993', byName('count')), /integer/i)
  assert.throws(() => parseConditionValue(null, byName('total')), /non-null/i)
  assert.throws(() => parseConditionValue('1e3', byName('total')), /format/i)
  assert.throws(() => parseConditionValue('other', byName('category')), /choice/i)
})

test('switching condition role or field replaces an incompatible equality value', () => {
  let rows = updateFieldRequirement(createRequirementDraft(policy, schemas), 'rent_invoice', 'total', { requirement: 'conditional' }, schemas)
  rows = updateRequirementCondition(rows, 'rent_invoice', 'total', { field: 'approved', operator: 'equals' }, schemas)
  assert.equal(rows.find(row => row.field === 'total').when.value, false)
  rows = updateRequirementCondition(rows, 'rent_invoice', 'total', { field: 'count' }, schemas)
  assert.equal(rows.find(row => row.field === 'total').when.value, 0)
  rows = updateRequirementCondition(rows, 'rent_invoice', 'total', { role: 'tax_invoice' }, schemas)
  assert.equal(rows.find(row => row.field === 'total').when.field, 'reference')
  assert.equal(rows.find(row => row.field === 'total').when.value, '')
})

test('serialization supplies stable reasons and refuses incomplete or invalid predicates', () => {
  const rows = createRequirementDraft(policy, schemas)
  const changed = updateFieldRequirement(rows, 'rent_invoice', 'total', { requirement: 'required', reason: '' }, schemas)
  assert.match(serializeRequirements(changed, schemas).find(row => row.field === 'total').reason, /Total/)
  assert.throws(() => serializeRequirements([...rows, { role: 'rent_invoice', field: 'extensions', requirement: 'required', reason: 'Invalid' }], schemas), /unsupported/i)
  assert.throws(() => serializeRequirements([{ role: 'rent_invoice', field: 'total', requirement: 'conditional', when: { role: 'rent_invoice', field: 'total', operator: 'equals', value: null } }], schemas), /non-null/i)
})

test('mode changes replace server default explanations while retaining a custom explanation', () => {
  const rows = createRequirementDraft({ requirements: [
    { role: 'rent_invoice', field: 'invoice_number', requirement: 'required', reason: 'Required by the host reconciliation policy.', when: null },
    { role: 'rent_invoice', field: 'total', requirement: 'optional', reason: 'Optional source field under the current host policy.', when: null },
    { role: 'rent_invoice', field: 'category', requirement: 'optional', reason: 'Team-defined explanation.', when: null },
  ] }, schemas)
  const optional = updateFieldRequirement(rows, 'rent_invoice', 'invoice_number', { requirement: 'optional' }, schemas)
  assert.match(optional.find(row => row.field === 'invoice_number').reason, /may be left blank/)
  const required = updateFieldRequirement(optional, 'rent_invoice', 'total', { requirement: 'required' }, schemas)
  assert.match(required.find(row => row.field === 'total').reason, /Total is required/)
  const custom = updateFieldRequirement(required, 'rent_invoice', 'category', { requirement: 'required' }, schemas)
  assert.equal(custom.find(row => row.field === 'category').reason, 'Team-defined explanation.')
})

test('an invoice-only edit never turns inherited required tax fields into explicit overrides', () => {
  const base_requirements = [
    ...policy.requirements,
    { role: 'tax_invoice', field: 'reference', requirement: 'required', reason: 'Required by the host reconciliation policy.' },
  ]
  const saved = { ...policy, requirements: base_requirements, base_requirements, overrides: [] }
  const rows = updateFieldRequirement(createRequirementDraft(saved, schemas), 'rent_invoice', 'total', { requirement: 'required' }, schemas)
  const output = serializeRequirementOverrides(rows, schemas, saved)
  assert.equal(output.length, 1)
  assert.equal(output[0].role, 'rent_invoice')
  assert.equal(output[0].field, 'total')
  assert.equal(requirementUsesHostDefault(rows.find(row => row.role === 'tax_invoice'), schemas, saved), true)
})

test('existing explicit overrides survive saves even when equal to a host default', () => {
  const tax = { role: 'tax_invoice', field: 'reference', requirement: 'required', reason: 'Tax document is explicitly mandatory.' }
  const saved = { ...policy, requirements: [...policy.requirements, tax], base_requirements: [...policy.requirements, { ...tax, reason: 'Required by the host reconciliation policy.' }], overrides: [tax] }
  const rows = createRequirementDraft(saved, schemas)
  assert.equal(serializeRequirementOverrides(rows, schemas, saved).length, 1)
  assert.equal(serializeRequirementOverrides(rows, schemas, saved)[0].reason, tax.reason)
  assert.equal(requirementUsesHostDefault(tax, schemas, saved), false)
})

test('an inherited reason-only edit does not change the executable presence policy', () => {
  const saved = { ...policy, base_requirements: policy.requirements, overrides: [] }
  const rows = updateFieldRequirement(createRequirementDraft(saved, schemas), 'rent_invoice', 'invoice_number', { reason: 'A different label.' }, schemas)
  assert.deepEqual(serializeRequirementOverrides(rows, schemas, saved), [])
})
