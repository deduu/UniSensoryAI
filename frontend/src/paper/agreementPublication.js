const ASSIGNED_IDENTITY = new Set(['vendor_id', 'store_id', 'contract_number'])

/** Check publication presence without copying assigned IDs into extracted source values. */
export function missingPublicationFields(version, context) {
  const terms = version?.draft?.terms || {}
  const required = [
    ...(context?.agreement_required_fields || []),
    ...(context?.agreement_required_fields_by_rent_type?.[terms.rent_type] || []),
  ]
  return [...new Set(required)].filter(key => {
    const value = ASSIGNED_IDENTITY.has(key) ? version?.identity?.[key] : terms[key]
    return value == null || value === '' || (typeof value === 'object' && Object.keys(value).length === 0)
  })
}
