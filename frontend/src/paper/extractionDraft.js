const clone = value => JSON.parse(JSON.stringify(value))
const identityKeys = ['vendor_id', 'store_id', 'contract_number']

/** Preserve all extraction issues while avoiding duplicate envelope copies. */
export function extractionWarnings(record) {
  const result = record?.result
  const issues = [...(result?.document?.warnings || []), ...(result?.fields?.warnings || []), ...(result?.warnings || [])]
  return clone([...new Map(issues.map(issue => [JSON.stringify(issue), issue])).values()])
}

/** Only a completed extraction with matching canonical fields can prefill a draft. */
export function canPrepareDraft(record) {
  const name = record?.schema_name?.replace(/^paper\./, '')
  return record?.status === 'completed'
    && ['rent_agreement', 'rent_invoice'].includes(name)
    && record?.result?.fields?.schema_id === `paper.${name}`
    && !!record?.result?.fields?.data && !!record?.result?.document?.document_id
}

function source(record, name) {
  if (record?.status !== 'completed' || record?.schema_name?.replace(/^paper\./, '') !== name || !record?.result?.document?.document_id || (record.result.fields && (!canPrepareDraft(record) || record.result.fields.schema_id !== `paper.${name}`))) throw new Error('Validated canonical fields are unavailable for this draft.')
  const data = clone(record.result.fields?.data || {})
  return {
    data, documentId: record.result.document.document_id,
    identity: Object.fromEntries(identityKeys.map(key => [key, data[key] ?? ''])),
    evidence: clone(record.result.fields?.evidence || []), warnings: extractionWarnings(record),
  }
}

/** Copy extracted terms into an editable draft without altering immutable history. */
export function agreementFromExtraction(record) {
  const { data, documentId, identity, evidence, warnings } = source(record, 'rent_agreement')
  return {
    identity,
    draft: {
      schema_id: record.result.fields?.schema_id || 'paper.rent_agreement', schema_version: record.result.fields?.schema_version || '1',
      terms: data, effective_from: data.lease_start_date || '', effective_to: data.lease_end_date || '',
      source_document_ids: [documentId],
      evidence: evidence.map(item => ({ document_id: documentId, evidence: item })),
      extraction_warnings: warnings,
      change_reason: 'PDF extraction prepared for source review.',
    },
  }
}

/** Create a new invoice package; missing dates and host identifiers stay unknown. */
export function invoiceFromExtraction(record) {
  const { data, documentId, identity, evidence, warnings } = source(record, 'rent_invoice')
  return {
    identity,
    invoice: {
      source_document_id: documentId, fields: data, evidence, warnings,
      ...(/^[a-f0-9]{64}$/i.test(documentId) ? { content_sha256: documentId } : {}),
    },
    tax_invoices: [], utility_statements: [], supporting_documents: [],
  }
}
