/** Advisory UI gates. The server revalidates every decision and remains authoritative. */
export function uniqueFindingCodes(version) {
  return [...new Set((version?.assessment?.findings || []).map((finding) => finding.code))]
}

/** Replace an imported package in full; omitted optional roles are empty. */
export function replacePackage(value) {
  const result = JSON.parse(JSON.stringify(value))
  for (const role of ['tax_invoices', 'utility_statements', 'supporting_documents']) result[role] ??= []
  return result
}

/** Assign canonical routing IDs without manufacturing values in source documents. */
export function applyPackageIdentity(value, identity) {
  const result = replacePackage(value)
  result.identity = { ...identity }
  return result
}

export function reviewEligibility(version, latestVersion, context, selectedCodes = []) {
  let reason = ''
  if (!context?.can_decide_cases) reason = 'Your account does not have AP review permission.'
  else if (!version || version.version_number !== latestVersion) reason = 'Select the latest case version to record a decision.'
  else if (version.decision) reason = 'This version already has a recorded decision.'
  else if (context.policy_id && context.policy_version && (version.assessment?.policy_id !== context.policy_id || version.assessment?.policy_version !== context.policy_version)) reason = 'The matching requirements or policy have changed. Reassess this case before recording a decision.'
  else if (context.require_independent_case_approval && version.created_by === context.user_id) reason = 'A different reviewer must decide this version.'
  const canDecide = !reason
  const codes = uniqueFindingCodes(version)
  const unreviewable = codes.filter((code) => !(context?.override_codes || []).includes(code))
  if (canDecide) {
    if (version.duplicate_of) reason = 'Duplicate cases cannot be approved.'
    else if (!version.assessment.agreement_reference) reason = 'An approved agreement reference is required.'
    else if (unreviewable.length) reason = 'Correct the blocking findings and reassess before approval.'
    else if (codes.length !== selectedCodes.length || codes.some((code) => !selectedCodes.includes(code))) reason = 'Explicitly accept every permitted finding before approval.'
  }
  return { canDecide, canApprove: canDecide && !reason, reason, codes, unreviewable }
}
