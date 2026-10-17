import test from 'node:test'
import assert from 'node:assert/strict'
import {
  applyFieldValue, copyAgreementDraft, createSampleAgreement, createSamplePackage,
  fieldDefinitions, formatError, formatStatus, jsonEditorValidity, parseImport, sameIdentity, schemaByName,
} from '../src/paper/helpers.js'

test('samples are isolated, unique, and preserve monetary and account strings', () => {
  const first = createSampleAgreement()
  const second = createSampleAgreement()
  assert.notEqual(first.identity.contract_number, second.identity.contract_number)
  assert.equal(first.draft.terms.fixed_rent, '1000000.00')
  assert.equal(first.draft.terms.bank_account, '0012345678')
  assert.deepEqual(first.draft.extraction_warnings, [])
  assert.equal('warnings' in first.draft, false)
  const one = createSamplePackage(first.identity)
  const two = createSamplePackage(first.identity)
  assert.deepEqual(one.identity, first.identity)
  assert.notEqual(one.invoice.fields.invoice_number, two.invoice.fields.invoice_number)
  assert.equal(one.invoice.fields.total, '1100000.00')
  assert.equal(one.tax_invoices[0].fields.invoice_number, one.invoice.fields.invoice_number)
  assert.deepEqual(one.invoice.warnings, [])
  assert.equal('extraction_warnings' in one.invoice, false)
  assert.deepEqual(one.tax_invoices[0].warnings, [])
  assert.equal('extraction_warnings' in one.tax_invoices[0], false)
  one.identity.vendor_id = 'changed'
  assert.notEqual(first.identity.vendor_id, 'changed')
})

test('unapplied structured JSON blocks outer form submission until applied or discarded', () => {
  const value = { external: { preserved: true } }
  const applied = JSON.stringify(value, null, 2)
  assert.equal(jsonEditorValidity(applied, value), '')
  assert.match(jsonEditorValidity('{"external":{"preserved":false}}', value), /apply/i)
  assert.match(jsonEditorValidity('{', value, 'Enter valid JSON.'), /valid JSON/i)
  assert.equal(jsonEditorValidity(applied, value, ''), '')
  assert.equal(jsonEditorValidity('null', null), '')
  assert.match(jsonEditorValidity('{}', null), /apply/i)
})

test('package warning metadata uses the backend document contract and is preserved on import', () => {
  const pkg = createSamplePackage(createSampleAgreement().identity)
  pkg.invoice.warnings = [{code: 'source_warning', message: 'Review source', severity: 'warning'}]
  assert.deepEqual(parseImport(JSON.stringify(pkg), 'package').invoice.warnings, pkg.invoice.warnings)
  pkg.invoice.warnings = {}
  assert.throws(() => parseImport(JSON.stringify(pkg), 'package'), /warnings.*array/i)
})

test('sample scenarios expose missing tax and bank mismatches without changing identity', () => {
  const identity = createSampleAgreement().identity
  assert.equal(createSamplePackage(identity, 'missing_tax').tax_invoices.length, 0)
  const bank = createSamplePackage(identity, 'bank_mismatch')
  assert.equal(bank.invoice.fields.bank_account, '0099999999')
  assert.deepEqual(bank.identity, identity)
  assert.throws(() => createSamplePackage(identity, 'unknown'), /scenario/i)
})

test('catalog resolves server external schema envelopes by exact PAPER identity', () => {
  const definition = { type: 'object', properties: { vendor_id: { type: 'string' } } }
  const catalog = [{ schema_id: 'paper.rent_agreement', version: '1', json_schema: definition }]
  assert.equal(schemaByName(catalog, 'rent_agreement'), definition)
  assert.equal(schemaByName(catalog, 'paper.rent_agreement'), definition)
  assert.equal(schemaByName(catalog, 'tax_invoice'), null)
})

test('form descriptors resolve local definitions and nullable types, including Decimal strings', () => {
  const schema = {
    type: 'object', $defs: { Choice: { type: 'string', enum: ['fixed', 'mixed'] } },
    properties: {
      fixed_rent: { anyOf: [{ type: 'string', pattern: '^-?(?:0|[1-9][0-9]*)(?:\\.[0-9]+)?$' }, { type: 'null' }] },
      rent_type: { anyOf: [{ $ref: '#/$defs/Choice' }, { type: 'null' }] },
      date: { anyOf: [{ type: 'string', format: 'date' }, { type: 'null' }] },
      duration: { type: ['integer', 'null'] }, extensions: { type: 'object' },
    }, required: ['extensions'],
  }
  const fields = fieldDefinitions({ json_schema: schema })
  assert.equal(fields.find(f => f.name === 'fixed_rent').type, 'string')
  assert.equal(fields.find(f => f.name === 'fixed_rent').nullable, true)
  assert.deepEqual(fields.find(f => f.name === 'rent_type').enum, ['fixed', 'mixed'])
  assert.equal(fields.find(f => f.name === 'date').format, 'date')
  assert.equal(fields.find(f => f.name === 'duration').type, 'integer')
  assert.equal(fields.find(f => f.name === 'extensions').required, true)
})

test('field edits retain provenance, extension values, and numeric text precision', () => {
  const original = { fixed_rent: '1', extensions: { nested: { external: true } }, custom: 'retained' }
  const result = applyFieldValue(original, 'fixed_rent', '12345678901234567890.001', { type: 'string' })
  assert.equal(result.fixed_rent, '12345678901234567890.001')
  assert.deepEqual(result.extensions, original.extensions)
  assert.equal(result.custom, 'retained')
  assert.equal(original.fixed_rent, '1')
  assert.equal(applyFieldValue(result, 'fixed_rent', '', { type: 'string', nullable: true }).fixed_rent, null)
  assert.equal(applyFieldValue(result, 'duration', '12', { type: 'integer' }).duration, 12)
  assert.throws(() => applyFieldValue(result, 'duration', '12.5', { type: 'integer' }), /integer/i)
})

test('agreement JSON import preserves warning and evidence objects', () => {
  const sample = createSampleAgreement()
  sample.draft.evidence = [{ field_path: '/fixed_rent', document_id: 'source', quote: 'source wording' }]
  sample.draft.extraction_warnings = [{ code: 'review', message: 'Human review', severity: 'warning' }]
  sample.draft.terms.extensions = { deeply: { customer: ['kept'] } }
  assert.deepEqual(parseImport(JSON.stringify(sample), 'agreement'), sample)
})

test('import rejects malformed shape and invalid JSON with safe, readable messages', () => {
  assert.throws(() => parseImport('sensitive secret no json', 'agreement'), error => !error.message.includes('sensitive secret'))
  assert.throws(() => parseImport('[]', 'agreement'), /object/i)
  assert.throws(() => parseImport('{"identity":{},"draft":{}}', 'agreement'), /vendor/i)
  const sample = createSamplePackage(createSampleAgreement().identity)
  sample.invoice.fields = []
  assert.throws(() => parseImport(JSON.stringify(sample), 'package'), /fields/i)
  assert.throws(() => parseImport('{"__proto__":{"polluted":true}}', 'object'), /unsupported/i)
  assert.equal({}.polluted, undefined)
})

test('imports cannot change canonical identity during a revision', () => {
  const agreement = createSampleAgreement()
  const changed = structuredClone(agreement)
  changed.identity.vendor_id += '-other'
  assert.throws(() => parseImport(JSON.stringify(changed), 'agreement', agreement.identity), /identity/i)
  const packageValue = createSamplePackage(agreement.identity)
  assert.deepEqual(parseImport(JSON.stringify(packageValue), 'package', agreement.identity), packageValue)
  assert.equal(sameIdentity(agreement.identity, changed.identity), false)
})

test('duplicate source IDs and oversized source packages are rejected before import', () => {
  const pkg = createSamplePackage(createSampleAgreement().identity)
  pkg.tax_invoices[0].source_document_id = pkg.invoice.source_document_id
  assert.throws(() => parseImport(JSON.stringify(pkg), 'package'), /unique/i)
  pkg.tax_invoices = Array.from({length: 100}, (_, i) => ({ source_document_id: `source-${i}`, fields: {} }))
  assert.throws(() => parseImport(JSON.stringify(pkg), 'package'), /100/i)
})

test('copying a historical agreement creates an isolated editable draft without computed state', () => {
  const original = createSampleAgreement()
  const draft = copyAgreementDraft({ ...original, status: 'approved', approval: { reason: 'old' } })
  assert.deepEqual(draft, original.draft)
  draft.terms.extensions.fixed_rent_basis = 'per_invoice'
  assert.equal(original.draft.terms.extensions.fixed_rent_basis, 'monthly')
})

test('API errors render structured domain details and field validation without echoing input', () => {
  assert.equal(formatError({ data: { detail: { code: 'conflict', message: 'Refresh this version.' } } }), 'Refresh this version. (conflict)')
  assert.equal(formatError({ data: { detail: [{ loc: ['body', 'invoice', 'fields', 'currency'], msg: 'Invalid currency', input: 'SECRET' }] } }), 'invoice.fields.currency: Invalid currency')
  assert.equal(formatError(new Error('Request timed out')), 'Request timed out')
  assert.equal(formatError({}), 'Unable to complete this request. Please try again.')
  assert.equal(formatStatus('needs_review'), 'Needs review')
})
