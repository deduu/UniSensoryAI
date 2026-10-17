/** Resolve a document handoff against server history for the current account and host. */
export function resolveGroundingNavigation(state, documents) {
  const documentId = state?.groundingDoc?.id
  if (typeof documentId !== 'string' || !documentId || !documents.some(document => document.id === documentId)) return null

  // Route state carries intent only. Document content remains in scoped server history.
  const remainingState = { ...state }
  delete remainingState.groundingDoc
  return {
    documentId,
    state: Object.keys(remainingState).length ? remainingState : null,
  }
}

/** Preserve documents selected manually and avoid duplicate context/citations. */
export function appendGroundingDocument(selectedIds, documentId) {
  return selectedIds.includes(documentId) ? selectedIds : [...selectedIds, documentId]
}
