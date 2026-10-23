/** Keep source references outside canonical snapshots and verify their document identity. */
export function sourceForDraft(record, documentIds = []) {
  const id = record?.result?.document?.document_id
  return record?.job_id && id && documentIds.includes(id) ? record : null
}

/** Count original PDF pages, including pages outside an extracted range. */
export function pageCount(record) {
  const document = record?.result?.document
  const counts = [record?.page_count, document?.page_count, ...(document?.pages || []).map(page => page.page_number)]
  return Math.max(1, ...counts.filter(value => Number.isInteger(value) && value > 0))
}

/** Resolve exact evidence identifiers; ambiguous IDs and other documents stay unlinked. */
export function evidencePages(record, item) {
  const document = record?.result?.document
  const evidence = item?.evidence || item
  const ids = evidence?.source_ids || []
  if (!document || (item?.document_id && item.document_id !== document.document_id)) return { pages: [], unresolved: [...ids] }
  const index = new Map()
  for (const page of document.pages || []) {
    if (!Number.isInteger(page.page_number) || page.page_number < 1) continue
    for (const id of [
      ...(page.text_blocks || []).map(block => block.block_id),
      ...(page.images || []).map(image => image.asset_id),
      ...(page.tables || []).map(table => table.table_id),
    ]) {
      if (!id) continue
      if (!index.has(id)) index.set(id, new Set())
      index.get(id).add(page.page_number)
    }
  }
  const pages = new Set()
  const unresolved = []
  for (const id of ids) {
    const matches = index.get(id)
    if (matches?.size === 1) pages.add([...matches][0])
    else unresolved.push(id)
  }
  return { pages: [...pages].sort((a, b) => a - b), unresolved }
}

/** Collect a field's exact and child citations without borrowing support from parent values. */
export function fieldEvidencePages(record, fieldPath, evidence = record?.result?.fields?.evidence ?? []) {
  const pages = new Set()
  const unresolved = new Set()
  let citationCount = 0
  if (typeof fieldPath !== 'string' || !fieldPath.startsWith('/')) return { pages: [], unresolved: [], citationCount }
  for (const item of evidence) {
    const path = (item?.evidence || item)?.field_path
    if (!matchesFieldPath(path, fieldPath)) continue
    citationCount++
    const citation = evidencePages(record, item)
    citation.pages.forEach(page => pages.add(page))
    citation.unresolved.forEach(id => unresolved.add(id))
  }
  return { pages: [...pages].sort((a, b) => a - b), unresolved: [...unresolved], citationCount }
}

function matchesFieldPath(path, fieldPath) {
  return typeof path === 'string' && typeof fieldPath === 'string' && fieldPath.startsWith('/')
    && (path === fieldPath || path.startsWith(`${fieldPath}/`))
}

function matchesReviewQuery(values, query) {
  return !query || values.some(value => typeof value === 'string' && value.toLowerCase().includes(query))
}

/** Filter inspector items without changing evidence identity, citations or canonical data. */
export function projectReviewItems(record, options = {}) {
  const evidence = options.evidence ?? record?.result?.fields?.evidence ?? []
  const warnings = options.warnings ?? []
  const fieldPath = options.fieldPath ?? ''
  const pageNumber = Number.isInteger(options.pageNumber) && options.pageNumber > 0 ? options.pageNumber : null
  const query = typeof options.query === 'string' ? options.query.trim().toLowerCase() : ''
  return {
    evidence: evidence.map(item => ({ item, ...evidencePages(record, item) })).filter(citation => {
      const quote = citation.item?.evidence || citation.item
      return (!fieldPath || matchesFieldPath(quote?.field_path, fieldPath))
        && (!pageNumber || citation.pages.includes(pageNumber))
        && matchesReviewQuery([quote?.field_path, quote?.quote], query)
    }),
    warnings: warnings.filter(item => {
      const warningPage = Number.isInteger(item?.page_number) && item.page_number > 0 ? item.page_number : null
      return (!fieldPath || !item?.field_path || matchesFieldPath(item.field_path, fieldPath))
        && (!pageNumber || !warningPage || warningPage === pageNumber)
        && matchesReviewQuery([typeof item === 'string' ? item : '', item?.code, item?.message, item?.field_path], query)
    }),
  }
}

/** Resolve a current value by exact JSON pointer without substituting retained candidates. */
export function reviewFieldValue(data, pointer) {
  if (typeof pointer !== 'string' || !pointer.startsWith('/')) return undefined
  let value = data
  for (const token of pointer.slice(1).split('/')) {
    const key = token.replaceAll('~1', '/').replaceAll('~0', '~')
    if (value === null || typeof value !== 'object' || !Object.hasOwn(value, key)) return undefined
    value = value[key]
  }
  return value
}

/** Project one stored page and its exact citations without changing extraction or draft data. */
export function reviewPage(record, pageNumber, options = {}) {
  const document = record?.result?.document
  const page = document?.pages?.find(item => item.page_number === pageNumber) || null
  const quotes = options.evidence ?? record?.result?.fields?.evidence ?? []
  const data = options.data ?? record?.result?.fields?.data ?? {}
  const linked = quotes.map(item => ({ item, pages: evidencePages(record, item).pages }))
  const evidence = page ? linked.filter(item => item.pages.includes(pageNumber)).map(item => item.item) : []
  const paths = [...new Set(evidence.map(item => (item.evidence || item).field_path).filter(path => typeof path === 'string' && path.startsWith('/')))]
  return {
    page,
    text: (page?.text_blocks || []).map(block => block.text).filter(text => typeof text === 'string' && text.trim()).join('\n\n'),
    evidence,
    fields: paths.map(fieldPath => ({ fieldPath, value: reviewFieldValue(data, fieldPath) })),
    unlinkedEvidenceCount: linked.filter(item => !item.pages.length).length,
  }
}
