import { useId } from 'react'

/** Collect reviewer-owned approval details without assigning policy or classification. */
export default function AgreementApprovalFields({ decision, onChange, inputClass }) {
  const helpId = useId()
  const update = (field, value) => onChange(current => ({ ...current, [field]: value }))

  return <div className="min-w-0 space-y-4">
    <div className="grid min-w-0 grid-cols-[repeat(auto-fit,minmax(min(100%,12rem),1fr))] gap-4">
      <label className="min-w-0 text-sm text-ink-muted">Classification
        <select className={inputClass} value={decision.classification} required onChange={event => update('classification', event.target.value)}>
          <option value="">Choose classification</option>
          <option value="psak73">PSAK 73</option>
          <option value="non_psak73">Non-PSAK 73</option>
        </select>
      </label>
      <label className="min-w-0 text-sm text-ink-muted">Accounting policy reference
        <input className={inputClass} value={decision.rule_set_id} required maxLength={128} aria-describedby={helpId} onChange={event => update('rule_set_id', event.target.value)} />
      </label>
      <label className="min-w-0 text-sm text-ink-muted">Policy revision
        <input className={inputClass} value={decision.rule_set_version} required maxLength={128} aria-describedby={helpId} onChange={event => update('rule_set_version', event.target.value)} />
      </label>
    </div>
    <div className="min-w-0 rounded-lg bg-surface-muted p-3 text-xs text-ink-muted">
      <p id={helpId}>Enter your organization’s approved accounting policy reference and revision. These references are recorded with your decision; the system does not check them against a policy catalog.</p>
      <details className="paper-disclosure mt-2">
        <summary className="cursor-pointer font-medium text-ink">Why are policy details required?</summary>
        <p className="mt-2">They identify the policy you used for this classification so a later reviewer can understand the approval. They do not select the invoice matching rules or automatically determine the classification.</p>
      </details>
    </div>
    <label className="block min-w-0 text-sm text-ink-muted">Review reason
      <textarea rows={2} className={inputClass} value={decision.reason} required maxLength={2000} onChange={event => update('reason', event.target.value)} />
    </label>
  </div>
}
