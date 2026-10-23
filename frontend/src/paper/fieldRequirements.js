import { fieldDefinitions, schemaByName } from './helpers.js'

export const MATCH_DOCUMENT_TYPES = [
  { role: 'rent_invoice', label: 'Rent invoice' },
  { role: 'tax_invoice', label: 'Tax invoice' },
  { role: 'utility_statement', label: 'Utility statement' },
  { role: 'supporting_document', label: 'Supporting document' },
]
const MODES = ['required', 'optional', 'conditional']
const OPERATORS = ['present', 'absent', 'equals']
const HOST_DEFAULT_REASONS = ['Required by the host reconciliation policy.', 'Optional source field under the current host policy.']
const key = row => `${row.role}:${row.field}`

/** Return the bounded scalar fields accepted by the matching policy. */
export function requirementFields(schemas, role) {
  if (!MATCH_DOCUMENT_TYPES.some(item => item.role === role)) return []
  return fieldDefinitions(schemaByName(schemas, role)).filter(field => field.name !== 'extensions' && ['string', 'number', 'integer', 'boolean'].includes(field.type))
}

function defaultReason(label, requirement) {
  if (requirement === 'required') return `${label} is required for document matching.`
  if (requirement === 'conditional') return `${label} is required when the selected condition applies.`
  return `${label} may be left blank for document matching.`
}

/** Add optional catalog fields without modifying the saved policy object. */
export function createRequirementDraft(policy, schemas) {
  const saved = new Map((policy?.requirements || []).map(row => [key(row), row]))
  return MATCH_DOCUMENT_TYPES.flatMap(({ role }) => requirementFields(schemas, role).map(field => {
    const existing = saved.get(`${role}:${field.name}`)
    return existing ? { ...existing, ...(existing.when ? { when: { ...existing.when } } : {}) } : { role, field: field.name, requirement: 'optional', reason: defaultReason(field.label, 'optional') }
  }))
}

/** Keep the draft independent of the visible document-type tab. */
export function updateFieldRequirement(rows, role, field, patch, schemas) {
  return rows.map(row => {
    if (row.role !== role || row.field !== field) return row
    const next = { ...row, ...patch }
    const definition = requirementFields(schemas, role).find(item => item.name === field)
    if (patch.requirement && patch.requirement !== row.requirement) {
      const automaticReason = HOST_DEFAULT_REASONS.includes(row.reason) || MODES.some(mode => row.reason === defaultReason(definition?.label || field, mode))
      if (automaticReason || !row.reason) next.reason = defaultReason(definition?.label || field, next.requirement)
    }
    if (next.requirement === 'conditional') next.when ||= { role, field, operator: 'present' }
    else delete next.when
    return next
  })
}

function firstValue(definition) {
  if (definition?.enum) return definition.enum.find(value => value !== null) ?? ''
  if (definition?.type === 'boolean') return false
  if (['number', 'integer'].includes(definition?.type)) return 0
  return ''
}

/** Remove stale values whenever a predicate changes type or stops using equality. */
export function updateRequirementCondition(rows, role, field, patch, schemas) {
  return rows.map(row => {
    if (row.role !== role || row.field !== field) return row
    const previous = row.when || { role, field, operator: 'present' }
    const when = { ...previous, ...patch }
    const fields = requirementFields(schemas, when.role)
    if (when.role !== previous.role) when.field = fields[0]?.name || ''
    if (when.operator !== 'equals') delete when.value
    else if (when.role !== previous.role || when.field !== previous.field || previous.operator !== 'equals') when.value = firstValue(fields.find(item => item.name === when.field))
    return { ...row, when }
  })
}

/** Parse equality using schema scalar types, retaining exact decimal strings. */
export function parseConditionValue(raw, definition) {
  if (raw == null) throw new Error('Equality requires a non-null value. Use is absent to check missing fields.')
  if (!definition) throw new Error('Choose a supported condition field.')
  let value = raw
  if (definition.type === 'boolean') {
    if (![true, false, 'true', 'false'].includes(raw)) throw new Error('Choose true or false.')
    value = raw === true || raw === 'true'
  } else if (['integer', 'number'].includes(definition.type)) {
    if (String(raw).trim() === '') throw new Error('Enter a number for this condition.')
    value = Number(raw)
    if (!Number.isFinite(value)) throw new Error('Enter a finite number.')
    if (definition.type === 'integer' && !Number.isSafeInteger(value)) throw new Error('Enter a whole integer within the supported range.')
    if (definition.minimum !== undefined && value < definition.minimum || definition.exclusiveMinimum !== undefined && value <= definition.exclusiveMinimum) throw new Error('Condition value is below the supported minimum.')
    if (definition.maximum !== undefined && value > definition.maximum || definition.exclusiveMaximum !== undefined && value >= definition.exclusiveMaximum) throw new Error('Condition value is above the supported maximum.')
  } else {
    if (typeof raw !== 'string') throw new Error('Enter a text value for this condition.')
    if (raw.length < (definition.minLength || 0) || raw.length > (definition.maxLength || 4000)) throw new Error('Condition text has an unsupported length.')
    if (definition.pattern && !new RegExp(definition.pattern).test(raw)) throw new Error('Condition value does not match the field format.')
  }
  if (definition.enum && !definition.enum.some(choice => Object.is(choice, value))) throw new Error('Choose a supported field choice.')
  return value
}

/** Build only the supported server contract, never leaking stale predicates. */
export function serializeRequirements(rows, schemas) {
  return rows.map(row => {
    const definition = requirementFields(schemas, row.role).find(item => item.name === row.field)
    if (!definition || !MODES.includes(row.requirement)) throw new Error('A field requirement references an unsupported field or mode.')
    const result = { role: row.role, field: row.field, requirement: row.requirement, reason: row.reason?.trim() || defaultReason(definition.label, row.requirement) }
    if (result.reason.length > 4000) throw new Error('A field requirement reason exceeds 4000 characters.')
    if (row.requirement === 'conditional') {
      const predicate = row.when
      const conditionField = requirementFields(schemas, predicate?.role).find(item => item.name === predicate?.field)
      if (!conditionField || !OPERATORS.includes(predicate?.operator)) throw new Error(`Choose a complete condition for ${definition.label}.`)
      result.when = { role: predicate.role, field: predicate.field, operator: predicate.operator }
      if (predicate.operator === 'equals') {
        try { result.when.value = parseConditionValue(predicate.value, conditionField) }
        catch (failure) { throw new Error(`${definition.label}: ${failure.message}`) }
      }
    }
    return result
  })
}

function samePresenceRule(first, second) {
  return first?.requirement === second?.requirement && JSON.stringify(first?.when || null) === JSON.stringify(second?.when || null)
}

function hostRequirements(policy, schemas) {
  return serializeRequirements(createRequirementDraft({ requirements: policy?.base_requirements || policy?.requirements || [] }, schemas), schemas)
}

/** Inherited explanation edits must not accidentally create executable requirements. */
export function requirementUsesHostDefault(row, schemas, policy) {
  if ((policy?.overrides || []).some(override => key(override) === key(row))) return false
  try {
    const normalized = serializeRequirements([row], schemas)[0]
    const base = hostRequirements(policy, schemas).find(item => key(item) === key(row))
    return samePresenceRule(normalized, base)
  } catch { return false }
}

/** Keep inherited defaults out of the raw override policy used by the engine. */
export function serializeRequirementOverrides(rows, schemas, policy) {
  const explicit = new Set((policy?.overrides || []).map(key))
  const base = new Map(hostRequirements(policy, schemas).map(row => [key(row), row]))
  return serializeRequirements(rows, schemas).filter(row => explicit.has(key(row)) || !samePresenceRule(row, base.get(key(row))))
}

export function requirementDraftChanged(saved, draft) {
  return JSON.stringify(saved) !== JSON.stringify(draft)
}
