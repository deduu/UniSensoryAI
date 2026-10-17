const IDENTITY_KEYS = ['vendor_id', 'store_id', 'contract_number']
const DOCUMENT_COLLECTIONS = ['tax_invoices', 'utility_statements', 'supporting_documents']
let sampleSequence = 0

const isObject = value => value !== null && typeof value === 'object' && !Array.isArray(value)
const clone = value => JSON.parse(JSON.stringify(value))
const uniqueSuffix = () => {
  sampleSequence += 1
  return globalThis.crypto?.randomUUID?.().slice(0, 8) || `${Date.now().toString(36)}-${sampleSequence}`
}

export function formatStatus(status) {
  const text = String(status || 'unknown').replaceAll('_', ' ')
  return text.charAt(0).toUpperCase() + text.slice(1)
}

/** Render API validation details without echoing the submitted document. */
export function formatError(error) {
  const detail = error?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail.slice(0, 12).map(item => {
      const location = Array.isArray(item?.loc) ? item.loc.filter(part => part !== 'body').join('.') : ''
      return `${location ? `${location}: ` : ''}${typeof item?.msg === 'string' ? item.msg : 'Invalid value'}`
    }).join('; ')
  }
  if (isObject(detail) && typeof detail.message === 'string') {
    return `${detail.message}${typeof detail.code === 'string' ? ` (${detail.code})` : ''}`
  }
  return typeof error?.message === 'string' && error.message !== '[object Object]'
    ? error.message : 'Unable to complete this request. Please try again.'
}

export function sameIdentity(left, right) {
  return isObject(left) && isObject(right) && IDENTITY_KEYS.every(key => left[key] === right[key])
}

/** A native form control may not submit while its JSON edits remain unapplied. */
export function jsonEditorValidity(text, value, error = '') {
  if (error) return error
  return text === JSON.stringify(value === undefined ? {} : value, null, 2) ? '' : 'Apply the JSON edits or discard them before saving.'
}

/** Parse structured schema edits without converting an explicit unknown to an object. */
export function parseStructuredValue(text, definition) {
  let parsed
  try { parsed = JSON.parse(text) } catch { throw new Error('Enter valid JSON before applying this field.') }
  if (parsed === null && definition.nullable) return null
  if (definition.type === 'array' ? !Array.isArray(parsed) : parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error(`Enter a JSON ${definition.type === 'array' ? 'array' : 'object'}${definition.nullable ? ' or null for unknown' : ''}.`)
  }
  return parsed
}

/** Synthetic fixtures populate local forms only; callers explicitly save them. */
export function createSampleAgreement(identity) {
  const suffix = uniqueSuffix()
  const canonical = identity ? clone(identity) : {
    vendor_id: `DEMO-VENDOR-${suffix}`,
    store_id: 'DEMO-STORE',
    contract_number: `DEMO-RA-2026-${suffix}`,
  }
  return {
    identity: canonical,
    draft: {
      terms: {
        vendor_name: 'Synthetic landlord', ...clone(canonical),
        lease_start_date: '2026-01-01', lease_end_date: '2026-12-31',
        payment_schedule: 'Monthly', rent_type: 'fixed', currency: 'IDR',
        fixed_rent: '1000000.00', bank_account: '0012345678',
        extensions: { fixed_rent_basis: 'monthly' },
      },
      effective_from: '2026-01-01', effective_to: '2026-12-31',
      source_document_ids: [`demo-agreement-${suffix}`],
      evidence: [], extraction_warnings: [],
      change_reason: 'Synthetic UI test agreement',
    },
  }
}

export function createSamplePackage(identity, scenario = 'matched') {
  if (!['matched', 'missing_tax', 'bank_mismatch', 'amount_mismatch'].includes(scenario)) {
    throw new Error('Unknown sample scenario.')
  }
  const suffix = uniqueSuffix()
  const canonical = identity ? clone(identity) : createSampleAgreement().identity
  const invoiceNumber = `DEMO-INV-${suffix}`
  const pkg = {
    identity: canonical,
    invoice: {
      source_document_id: `demo-invoice-${suffix}`,
      fields: {
        ...clone(canonical), invoice_number: invoiceNumber, invoice_date: '2026-06-01',
        service_period_start: '2026-06-01', service_period_end: '2026-06-30',
        currency: 'IDR', subtotal: '1000000.00', tax_amount: '100000.00', total: '1100000.00',
        bank_account: '0012345678',
      },
      evidence: [], warnings: [],
    },
    tax_invoices: [{
      source_document_id: `demo-tax-${suffix}`,
      fields: {
        ...clone(canonical), invoice_number: invoiceNumber, tax_invoice_number: `DEMO-TAX-${suffix}`,
        tax_invoice_date: '2026-06-01', currency: 'IDR', taxable_amount: '1000000.00',
        tax_amount: '100000.00', total: '1100000.00',
      },
      evidence: [], warnings: [],
    }],
    utility_statements: [], supporting_documents: [],
  }
  if (scenario === 'missing_tax') pkg.tax_invoices = []
  if (scenario === 'bank_mismatch') pkg.invoice.fields.bank_account = '0099999999'
  if (scenario === 'amount_mismatch') {
    for (const fields of [pkg.invoice.fields, pkg.tax_invoices[0].fields]) {
      if ('subtotal' in fields) fields.subtotal = '1200000.00'
      if ('taxable_amount' in fields) fields.taxable_amount = '1200000.00'
      fields.total = '1300000.00'
    }
  }
  return pkg
}

export function copyAgreementDraft(version) {
  if (!isObject(version?.draft)) throw new Error('Agreement draft is unavailable.')
  return clone(version.draft)
}

export function schemaByName(catalog, name) {
  if (!Array.isArray(catalog)) return null
  const id = name.startsWith('paper.') ? name : `paper.${name}`
  return catalog.find(item => item.schema_id === id)?.json_schema || null
}

/** Resolve only local schema definitions. Complex values retain JSON editing. */
export function resolveSchema(definition, root, visited = new Set()) {
  if (!isObject(definition)) return {}
  let schema = { ...definition }
  if (schema.$ref) {
    const reference = schema.$ref
    if (typeof reference !== 'string' || !reference.startsWith('#/') || visited.has(reference)) return { type: 'object' }
    const next = new Set(visited)
    next.add(reference)
    const pointed = reference.slice(2).split('/').reduce((value, key) => value?.[key.replaceAll('~1', '/').replaceAll('~0', '~')], root)
    schema = { ...resolveSchema(pointed, root, next), ...schema }
    delete schema.$ref
  }
  if (Array.isArray(schema.allOf)) {
    const branches = schema.allOf.map(branch => resolveSchema(branch, root, visited))
    schema = branches.reduce((result, branch) => ({
      ...result, ...branch,
      properties: { ...result.properties, ...branch.properties },
      required: [...new Set([...(result.required || []), ...(branch.required || [])])],
    }), schema)
  }
  const choices = schema.anyOf || schema.oneOf
  if (Array.isArray(choices)) {
    const resolved = choices.map(branch => resolveSchema(branch, root, visited))
    const nullable = resolved.some(branch => branch.type === 'null')
    const nonNull = resolved.filter(branch => branch.type !== 'null')
    schema = { ...(nonNull[0] || {}), ...schema, nullable }
  }
  if (Array.isArray(schema.type)) {
    schema.nullable = schema.type.includes('null')
    schema.type = schema.type.find(type => type !== 'null') || 'null'
  }
  return schema
}

export function fieldDefinitions(envelope) {
  const root = envelope?.json_schema || envelope
  const schema = resolveSchema(root, root)
  return Object.entries(schema.properties || {}).map(([name, definition]) => ({
    ...resolveSchema(definition, root), name,
    label: definition.title || name.replaceAll('_', ' ').replace(/^./, letter => letter.toUpperCase()),
    required: (schema.required || []).includes(name),
  })).sort((left, right) => Number(left.name === 'extensions') - Number(right.name === 'extensions'))
}

export function applyFieldValue(current, name, raw, definition) {
  let value = raw
  if (raw === '' && definition.nullable) value = null
  else if (definition.type === 'integer' && raw !== '') {
    value = Number(raw)
    if (!Number.isSafeInteger(value)) throw new Error('Enter a whole integer within the supported range.')
  } else if (definition.type === 'number' && raw !== '') {
    value = Number(raw)
    if (!Number.isFinite(value)) throw new Error('Enter a finite number.')
  }
  return { ...current, [name]: value }
}

function assertObject(value, label) {
  if (!isObject(value)) throw new Error(`${label} must be a JSON object.`)
}

function validateIdentity(identity) {
  assertObject(identity, 'Canonical identity')
  for (const key of IDENTITY_KEYS) {
    if (typeof identity[key] !== 'string' || !identity[key].trim() || identity[key].length > 128) {
      throw new Error(`Canonical ${key.replaceAll('_', ' ')} must be a nonempty string of at most 128 characters.`)
    }
  }
}

function validateDocument(document, label) {
  assertObject(document, label)
  if (typeof document.source_document_id !== 'string' || !document.source_document_id.trim()) {
    throw new Error(`${label} requires a source document ID.`)
  }
  assertObject(document.fields, `${label} fields`)
  for (const key of ['evidence', 'warnings']) {
    if (document[key] !== undefined && !Array.isArray(document[key])) throw new Error(`${label} ${key} must be an array.`)
  }
}

/** Validate import structure; the backend remains the full contract authority. */
export function parseImport(text, kind = 'object', currentIdentity) {
  if (typeof text !== 'string' || text.length > 2 * 1024 * 1024) throw new Error('JSON import exceeds the supported 2 MiB limit.')
  let value
  let nodes = 0
  try {
    value = JSON.parse(text, (key, item) => {
      if (['__proto__', 'prototype', 'constructor'].includes(key)) throw new Error('Unsafe key')
      nodes += 1
      if (nodes > 50000) throw new Error('Size budget')
      return item
    })
  } catch {
    throw new Error('Enter valid JSON without unsupported keys, within the import size limit.')
  }
  assertObject(value, 'Imported value')
  if (kind === 'object') return value
  if (!['agreement', 'package'].includes(kind)) throw new Error('Unsupported JSON import type.')
  validateIdentity(value.identity)
  if (currentIdentity && !sameIdentity(value.identity, currentIdentity)) throw new Error('Canonical identity cannot change in a revision. Create a new record for a different identity.')
  if (kind === 'agreement') {
    assertObject(value.draft, 'Agreement draft')
    assertObject(value.draft.terms, 'Agreement terms')
    if (!Array.isArray(value.draft.source_document_ids) || !value.draft.source_document_ids.length || value.draft.source_document_ids.some(id => typeof id !== 'string' || !id.trim())) {
      throw new Error('Agreement source document IDs must be a nonempty array of strings.')
    }
    for (const field of ['effective_from', 'effective_to', 'change_reason']) {
      if (typeof value.draft[field] !== 'string' || !value.draft[field].trim()) throw new Error(`Agreement ${field.replaceAll('_', ' ')} is required.`)
    }
    for (const field of ['evidence', 'extraction_warnings']) {
      if (value.draft[field] !== undefined && !Array.isArray(value.draft[field])) throw new Error(`Agreement ${field} must be an array.`)
    }
  } else {
    validateDocument(value.invoice, 'Rent invoice')
    const documents = [value.invoice]
    for (const collection of DOCUMENT_COLLECTIONS) {
      if (value[collection] !== undefined && !Array.isArray(value[collection])) throw new Error(`${collection} must be an array.`)
      for (const document of value[collection] || []) {
        validateDocument(document, collection.replaceAll('_', ' '))
        documents.push(document)
      }
    }
    if (documents.length > 100) throw new Error('Invoice packages support at most 100 documents.')
    const ids = documents.map(document => document.source_document_id)
    if (new Set(ids).size !== ids.length) throw new Error('Source document IDs must be unique within a package.')
  }
  return value
}
