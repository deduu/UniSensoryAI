/** Search a read-only projection; canonical values and pointer identity stay unchanged. */
export function filterFieldValues(data, query = '') {
  if (!data || typeof data !== 'object' || Array.isArray(data)) return []
  const normalized = query.trim().toLowerCase()
  return Object.entries(data)
    .filter(([key, value]) => !normalized || `${key.replaceAll('_', ' ')} ${key} ${JSON.stringify(value) ?? ''}`.toLowerCase().includes(normalized))
    .map(([key, value]) => ({ fieldPath: `/${key.replaceAll('~', '~0').replaceAll('/', '~1')}`, value }))
}
