import test from 'node:test'
import assert from 'node:assert/strict'
import { evidencePages, fieldEvidencePages, pageCount, projectReviewItems, reviewPage, sourceForDraft } from '../src/paper/sourceReview.js'

const source = {
  job_id: 'source-job', page_count: 38,
  result: { document: { document_id: 'source-hash', pages: [
    { page_number: 3, text_blocks: [{ block_id: 'paragraph/arbitrary' }, { block_id: 'repeated' }], images: [{ asset_id: 'signed-image' }], tables: [{ table_id: 'rent-table' }] },
    { page_number: 17, text_blocks: [{ block_id: 'payment-term' }, { block_id: 'repeated' }] },
  ] } },
}

test('evidence navigation resolves exact block, image and table IDs to original PDF pages', () => {
  assert.deepEqual(evidencePages(source, { source_ids: ['payment-term', 'paragraph/arbitrary', 'signed-image', 'rent-table'] }), { pages: [3, 17], unresolved: [] })
  assert.deepEqual(evidencePages(source, { source_ids: ['p9-guessed', 'repeated', 'payment-term'] }), { pages: [17], unresolved: ['p9-guessed', 'repeated'] })
})

test('qualified agreement evidence cannot link a different source document', () => {
  const evidence = { source_ids: ['payment-term'] }
  assert.deepEqual(evidencePages(source, { document_id: 'source-hash', evidence }), { pages: [17], unresolved: [] })
  assert.deepEqual(evidencePages(source, { document_id: 'other-hash', evidence }), { pages: [], unresolved: ['payment-term'] })
})

test('draft source attachment follows document ownership without modifying canonical snapshots', () => {
  const draft = { source_document_ids: ['source-hash'], terms: { monthly_rent: '123.45' } }
  const before = structuredClone(draft)
  assert.equal(sourceForDraft(source, draft.source_document_ids), source)
  assert.equal(sourceForDraft(source, ['other-hash']), null)
  assert.equal(sourceForDraft(null, draft.source_document_ids), null)
  assert.deepEqual(draft, before)
  assert.equal('source_job_id' in draft, false)
})

test('PDF navigation uses the full source page count and handles missing extraction metadata', () => {
  assert.equal(pageCount(source), 38)
  assert.equal(pageCount({ result: { document: { pages: [{ page_number: 7 }, { page_number: 2 }] } } }), 7)
  assert.equal(pageCount({ result: { document: { page_count: 12, pages: [] } } }), 12)
  assert.equal(pageCount(null), 1)
})

const paged = {
  ...source,
  result: { document: { ...source.result.document, pages: [
    { ...source.result.document.pages[0], text_blocks: [{ block_id: 'paragraph/arbitrary', text: 'Third page text.' }, { block_id: 'repeated', text: 'Repeated reference.' }] },
    { ...source.result.document.pages[1], text_blocks: [{ block_id: 'payment-term', text: 'Seventeenth page text.' }, { block_id: 'repeated', text: '' }] },
  ] }, fields: {
    data: { vendor_name: 'Example landlord', payment_schedule: 'Annual', extensions: { 'a/b': { '~key': 'Preserve exact value' } }, other_key_terms: ['First term', 'Second term'] },
    evidence: [
      { field_path: '/vendor_name', source_ids: ['paragraph/arbitrary'], quote: 'Example landlord' },
      { field_path: '/payment_schedule', source_ids: ['payment-term'], quote: 'Annual' },
      { field_path: '/other_key_terms/1', source_ids: ['payment-term', 'paragraph/arbitrary'], quote: 'Second term' },
      { field_path: '/extensions/a~1b/~0key', source_ids: ['signed-image'], quote: 'Preserve exact value' },
      { field_path: '/vendor_name', source_ids: ['repeated'], quote: 'Ambiguous' },
    ],
  } },
}

test('page review follows original page numbers and includes only exactly linked field values', () => {
  const before = structuredClone(paged)
  const third = reviewPage(paged, 3)
  assert.equal(third.text, 'Third page text.\n\nRepeated reference.')
  assert.deepEqual(third.fields, [
    { fieldPath: '/vendor_name', value: 'Example landlord' },
    { fieldPath: '/other_key_terms/1', value: 'Second term' },
    { fieldPath: '/extensions/a~1b/~0key', value: 'Preserve exact value' },
  ])
  const seventeenth = reviewPage(paged, 17)
  assert.equal(seventeenth.text, 'Seventeenth page text.')
  assert.deepEqual(seventeenth.fields.map(field => field.fieldPath), ['/payment_schedule', '/other_key_terms/1'])
  assert.equal(third.evidence.length, 3)
  assert.equal(third.unlinkedEvidenceCount, 1)
  assert.deepEqual(paged, before)
})

test('missing page extraction stays empty rather than borrowing another page or document text', () => {
  const missing = reviewPage(paged, 4)
  assert.equal(missing.page, null)
  assert.equal(missing.text, '')
  assert.deepEqual(missing.fields, [])
  assert.deepEqual(missing.evidence, [])
  assert.equal(reviewPage(null, 1).text, '')
})

test('editable values follow retained citations without accepting foreign or ambiguous links', () => {
  const evidence = [
    { document_id: 'source-hash', evidence: { field_path: '/vendor_name', source_ids: ['paragraph/arbitrary'], quote: 'Old source value' } },
    { document_id: 'other-hash', evidence: { field_path: '/payment_schedule', source_ids: ['paragraph/arbitrary'] } },
    { field_path: '/payment_schedule', source_ids: ['repeated'] },
  ]
  const current = { vendor_name: 'Unsaved reviewed value' }
  const review = reviewPage(paged, 3, { evidence, data: current })
  assert.deepEqual(review.fields, [{ fieldPath: '/vendor_name', value: 'Unsaved reviewed value' }])
  assert.equal(review.unlinkedEvidenceCount, 2)
  assert.equal(review.evidence[0].evidence.quote, 'Old source value')
})

test('page field pointers never read inherited properties and preserve null, zero, and missing values', () => {
  const evidence = ['/zero', '/unknown', '/missing', '/toString'].map(field_path => ({ field_path, source_ids: ['payment-term'] }))
  const review = reviewPage(paged, 17, { evidence, data: { zero: 0, unknown: null } })
  assert.deepEqual(review.fields.map(field => field.value), [0, null, undefined, undefined])
})

test('field shortcuts aggregate all exact and descendant citations into sorted unique pages', () => {
  const before = structuredClone(paged)
  assert.deepEqual(fieldEvidencePages(paged, '/other_key_terms'), { pages: [3, 17], unresolved: [], citationCount: 1 })
  assert.deepEqual(fieldEvidencePages(paged, '/vendor_name'), { pages: [3], unresolved: ['repeated'], citationCount: 2 })
  assert.deepEqual(paged, before)
})

test('field shortcuts respect pointer boundaries and document identity without inferring parent support', () => {
  const evidence = [
    { field_path: '/terms/1', source_ids: ['payment-term'] },
    { field_path: '/terms/10', source_ids: ['paragraph/arbitrary'] },
    { field_path: '/terms_extra', source_ids: ['signed-image'] },
    { field_path: '/terms', source_ids: ['rent-table'] },
    { document_id: 'other-hash', evidence: { field_path: '/terms/1', source_ids: ['signed-image'] } },
  ]
  assert.deepEqual(fieldEvidencePages(paged, '/terms/1', evidence), { pages: [17], unresolved: ['signed-image'], citationCount: 2 })
  assert.deepEqual(fieldEvidencePages(paged, '/terms/2', evidence), { pages: [], unresolved: [], citationCount: 0 })
  assert.deepEqual(fieldEvidencePages(paged, '/terms', evidence).pages, [3, 17])
})

test('source shortcuts preserve escaped external schema keys and report absent or unresolved evidence', () => {
  assert.deepEqual(fieldEvidencePages(paged, '/extensions/a~1b/~0key'), { pages: [3], unresolved: [], citationCount: 1 })
  assert.deepEqual(fieldEvidencePages(paged, '/extensions/a/b'), { pages: [], unresolved: [], citationCount: 0 })
  assert.deepEqual(fieldEvidencePages(null, '/vendor_name'), { pages: [], unresolved: [], citationCount: 0 })
  assert.deepEqual(fieldEvidencePages(paged, 'vendor_name'), { pages: [], unresolved: [], citationCount: 0 })
  const evidence = [{ field_path: '/unknown', source_ids: ['unresolved', 'unresolved'] }]
  assert.deepEqual(fieldEvidencePages(paged, '/unknown', evidence), { pages: [], unresolved: ['unresolved'], citationCount: 1 })
})

test('review inspector preserves all citations, multi-page links and unresolved evidence by default', () => {
  const before = structuredClone(paged)
  const result = projectReviewItems(paged)
  assert.equal(result.evidence.length, paged.result.fields.evidence.length)
  assert.equal(result.evidence[2].item, paged.result.fields.evidence[2])
  assert.deepEqual(result.evidence[2].pages, [3, 17])
  assert.deepEqual(result.evidence[4].unresolved, ['repeated'])
  assert.deepEqual(result.warnings, [])
  assert.deepEqual(projectReviewItems(null), { evidence: [], warnings: [] })
  assert.deepEqual(paged, before)
})

test('review inspector field filter uses exact pointer boundaries and retains unlinked foreign citations', () => {
  const evidence = [
    { field_path: '/terms', source_ids: ['rent-table'], quote: 'Parent' },
    { field_path: '/terms/1', source_ids: ['payment-term'], quote: 'Exact' },
    { field_path: '/terms/1/detail', source_ids: ['signed-image'], quote: 'Child' },
    { field_path: '/terms/10', source_ids: ['paragraph/arbitrary'], quote: 'Sibling' },
    { field_path: '/terms_extra', source_ids: ['paragraph/arbitrary'], quote: 'Other' },
    { document_id: 'other-hash', evidence: { field_path: '/terms/1', source_ids: ['signed-image'], quote: 'Foreign' } },
    { field_path: '/terms/1', source_ids: ['repeated'], quote: 'Ambiguous' },
  ]
  const filtered = projectReviewItems(paged, { evidence, fieldPath: '/terms/1' })
  assert.deepEqual(filtered.evidence.map(item => item.item), [evidence[1], evidence[2], evidence[5], evidence[6]])
  assert.deepEqual(filtered.evidence.map(item => item.pages), [[17], [3], [], []])
  assert.deepEqual(filtered.evidence[2].unresolved, ['signed-image'])
  assert.deepEqual(filtered.evidence[3].unresolved, ['repeated'])
  assert.equal(filtered.evidence[2].item, evidence[5])
})

test('review inspector preserves escaped pointer identity and searches only citation paths or quotes', () => {
  const evidence = [
    { field_path: '/extensions/a~1b/~0key', source_ids: ['signed-image'], quote: 'Escaped canonical key' },
    { field_path: '/extensions/a~1b/~0key/part', source_ids: ['payment-term'], quote: 'Child' },
    { field_path: '/extensions/a~1b/~0key_other', source_ids: ['payment-term'], quote: 'Other' },
    { field_path: '/extensions/a/b/~0key', source_ids: ['signed-image'], quote: 'Different key' },
  ]
  assert.deepEqual(projectReviewItems(paged, { evidence, fieldPath: '/extensions/a~1b/~0key' }).evidence.map(item => item.item), evidence.slice(0, 2))
  assert.deepEqual(projectReviewItems(paged, { evidence, query: '  ESCAPED CANONICAL  ' }).evidence.map(item => item.item), [evidence[0]])
  assert.equal(projectReviewItems(paged, { evidence, query: '/EXTENSIONS/A~1B/~0KEY/PART' }).evidence[0].item, evidence[1])
  assert.deepEqual(projectReviewItems(paged, { evidence, query: 'signed-image' }).evidence, [])
})

test('review inspector combines field, exact page and query filters without narrowing multi-page citations', () => {
  const multi = { field_path: '/terms/1', source_ids: ['payment-term', 'signed-image'], quote: 'Important contract clause' }
  const evidence = [
    multi,
    { document_id: 'other-hash', evidence: { field_path: '/terms/1', source_ids: ['payment-term'], quote: 'Important foreign clause' } },
    { field_path: '/terms/1', source_ids: ['repeated'], quote: 'Important ambiguous clause' },
    { field_path: '/terms/1', source_ids: ['rent-table'], quote: 'Important other page' },
    { field_path: '/terms/10', source_ids: ['payment-term'], quote: 'Important sibling' },
    { field_path: '/terms/1/detail', source_ids: ['payment-term'], quote: 'Different wording' },
  ]
  const before = structuredClone(evidence)
  const result = projectReviewItems(paged, { evidence, fieldPath: '/terms/1', pageNumber: 17, query: 'IMPORTANT' })
  assert.deepEqual(result.evidence, [{ item: multi, pages: [3, 17], unresolved: [] }])
  assert.equal(result.evidence[0].item, multi)
  assert.deepEqual(evidence, before)
  assert.equal(projectReviewItems(paged, { evidence, pageNumber: 4 }).evidence.length, 0)
  assert.equal(projectReviewItems(paged, { evidence, pageNumber: null }).evidence.length, 6)
  assert.equal(projectReviewItems(paged, { evidence, pageNumber: 0 }).evidence.length, 6)
})

test('review inspector keeps global warnings while combining field, page and text filters', () => {
  const warnings = [
    { field_path: '/terms', code: 'parent', message: 'Parent warning', page_number: 17 },
    { field_path: '/terms/1', code: 'specific', message: 'Needs important review', page_number: 17 },
    { field_path: '/terms/1/detail', code: 'child', message: 'Important details', page_number: 3 },
    { field_path: '/terms/10', code: 'sibling', message: 'Important sibling', page_number: 17 },
    { code: 'important_document', message: 'Global warning' },
    'Important legacy warning',
    { field_path: '/terms/1', code: 'page_unknown', message: 'Important unpaged warning' },
    { code: 'other_page', message: 'Important page warning', page_number: 3 },
  ]
  const before = structuredClone(warnings)
  const options = { warnings, fieldPath: '/terms/1', pageNumber: 17, query: 'important' }
  const result = projectReviewItems(paged, options)
  assert.deepEqual(result.warnings, [warnings[1], warnings[4], warnings[5], warnings[6]])
  assert.equal(result.warnings[0], warnings[1])
  assert.deepEqual(projectReviewItems(paged, { warnings, query: 'SPECIFIC' }).warnings, [warnings[1]])
  assert.deepEqual(projectReviewItems(paged, { warnings, query: '/TERMS/1/DETAIL' }).warnings, [warnings[2]])
  assert.deepEqual(warnings, before)
})
