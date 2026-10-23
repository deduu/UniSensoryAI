import SchemaFields from './SchemaFields'
import MoneyInput from './MoneyInput'
import { formatMoney } from '../../paper/money'
import { assertSavedInstallmentIds, patchInstallment, patchPaymentRule, removeInstallment } from '../../paper/installmentRules'

export const AGREEMENT_PAYMENT_FIELDS = ['installment_schedule', 'withholding_policy']

function Field({ label, value, onChange, type = 'text', required = true, money = false, currency, ...rest }) {
  return <label className="block text-xs font-medium text-ink-muted">{label}{money ? <MoneyInput aria-label={label} className="paper-input mt-1" value={value ?? ''} currency={currency} required={required} onChange={onChange} {...rest} /> : <input className="paper-input mt-1" type={type} value={value ?? ''} required={required} onChange={event => onChange(event.target.value)} {...rest} />}</label>
}

/** Reviewed versioned payment rules; source rent price and narrative remain intact. */
export default function AgreementPaymentRules({ schema, terms, onChange = () => {}, disabled = false, savedInstallmentIds = [] }) {
  const schedule = terms.installment_schedule
  const policy = terms.withholding_policy
  const setRule = (key, changes) => onChange(assertSavedInstallmentIds(patchPaymentRule(terms, key, changes), savedInstallmentIds))
  const setItem = (index, changes) => onChange(patchInstallment(terms, index, changes))
  const addItem = () => setRule('installment_schedule', { installments: [...(schedule?.installments || []), { installment_id: '', gross_amount: '', coverage_start: '', coverage_end: '', conditions: [] }] })
  if (disabled) return <section aria-label="Installment and withholding rules" className="min-w-0 space-y-4 rounded-xl border border-surface-border p-4">
    <div><h3 className="font-semibold text-ink">Installment and withholding rules</h3><p className="mt-1 text-xs text-ink-muted">Reviewed allocation and tax settings are separate from the printed payment narrative. Unknown settings require an explicit review decision.</p></div>
    {schedule?.source_discrepancy_note && <p className="paper-notice break-words">Source discrepancy requiring review: {schedule.source_discrepancy_note}</p>}
    <SchemaFields schema={schema} value={terms} disabled only={AGREEMENT_PAYMENT_FIELDS} idPrefix="payment-rules-read" />
  </section>
  return <section aria-label="Installment and withholding rules" className="min-w-0 space-y-4 rounded-xl border border-surface-border p-4">
    <div><h3 className="font-semibold text-ink">Installment and withholding rules</h3><p className="mt-1 text-sm text-ink-muted">{schedule ? `${schedule.installments?.length || 0} installments · ${schedule.total_gross === '' || schedule.total_gross == null ? 'Amount unknown' : formatMoney(schedule.total_gross, schedule.currency)} gross${schedule.currency ? '' : ' · Currency unknown'}` : 'No installment schedule'}{policy ? ` · Withholding rate ${policy.rate || 'unknown'}` : ''}</p></div>
    {disabled && schedule?.source_discrepancy_note && <p className="paper-notice break-words">Source discrepancy requiring review: {schedule.source_discrepancy_note}</p>}
    <details className="paper-disclosure" open={!disabled || undefined}><summary className="text-sm font-medium text-ink">{disabled ? 'Review payment rules and conditions' : 'Edit payment rules'}</summary><div className="mt-4 space-y-4">
    <details className="text-xs text-ink-muted"><summary>How these rules are used</summary><p className="mt-2 leading-5">These rules belong to this agreement version. Keep the source annual price and payment conditions. Review tax treatment and rounding explicitly before approval. Allocation dates are reviewed accounting coverage, not invoice service dates or contractual due dates.</p></details>
    <fieldset disabled={disabled} className="space-y-4">
      {!schedule ? <div className="space-y-2"><p className="text-sm text-ink-muted">No structured installment schedule. Existing monthly and per-invoice rules remain available.</p>{!disabled && <button type="button" className="paper-secondary" onClick={() => onChange({ ...terms, installment_schedule: { schedule_id: '', version: '1', currency: terms.currency || '', total_gross: '', source_reference: '', source_discrepancy_note: null, installments: [] } })}>Add installment schedule</button>}</div> : <div className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2"><h4 className="text-sm font-semibold">Cash installment schedule</h4>{!disabled && !savedInstallmentIds.length && <button type="button" className="paper-secondary" onClick={() => onChange({ ...terms, installment_schedule: null })}>Remove installment schedule</button>}</div>
        {savedInstallmentIds.length > 0 && <p className="text-xs text-ink-muted">Saved installment IDs stay fixed across versions to prevent duplicate billing. Amounts, allocation, and conditions can be corrected; new installments can be added.</p>}
        <details className="paper-disclosure rounded-lg bg-surface-muted p-3" open={!schedule.schedule_id || !schedule.source_reference || undefined}><summary className="text-xs font-medium">Schedule version and source reference</summary><div className="mt-3 space-y-3"><div className="grid gap-3 sm:grid-cols-2">
          <Field label="Schedule ID" value={schedule.schedule_id} onChange={value => setRule('installment_schedule', { schedule_id: value })} />
          <Field label="Schedule version" value={schedule.version} onChange={value => setRule('installment_schedule', { version: value })} />
        </div><Field label="Schedule source reference" value={schedule.source_reference} onChange={value => setRule('installment_schedule', { source_reference: value })} /></div></details>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Schedule currency" value={schedule.currency} maxLength={3} onChange={value => setRule('installment_schedule', { currency: value })} />
          <Field label="Stated total gross rent" value={schedule.total_gross} money currency={schedule.currency} onChange={value => setRule('installment_schedule', { total_gross: value })} />
        </div>
        <label className="block text-xs font-medium text-ink-muted">Source discrepancy note<textarea className="paper-input mt-1" rows={2} value={schedule.source_discrepancy_note ?? ''} onChange={event => setRule('installment_schedule', { source_discrepancy_note: event.target.value || null })} /></label>
        {(schedule.installments || []).map((item, index) => <div key={index} className="space-y-3 rounded-lg border border-surface-border p-3">
          <div className="flex items-center justify-between gap-2"><h5 className="text-sm font-semibold">Installment {index + 1}</h5>{!disabled && !savedInstallmentIds.includes(item.installment_id) && <button type="button" className="paper-secondary" onClick={() => onChange(removeInstallment(terms, index))}>Remove installment {index + 1}</button>}</div>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label={`Installment ${index + 1} ID`} value={item.installment_id} disabled={savedInstallmentIds.includes(item.installment_id)} onChange={value => setItem(index, { installment_id: value })} />
            <Field label={`Installment ${index + 1} gross amount`} value={item.gross_amount} money currency={schedule.currency} onChange={value => setItem(index, { gross_amount: value })} />
            <Field label={`Installment ${index + 1} allocation start`} type="date" value={item.coverage_start} onChange={value => setItem(index, { coverage_start: value })} />
            <Field label={`Installment ${index + 1} allocation end`} type="date" min={item.coverage_start || undefined} value={item.coverage_end} onChange={value => setItem(index, { coverage_end: value })} />
          </div>
          {(item.conditions || []).map((condition, conditionIndex) => <div className="space-y-2" key={conditionIndex}><label className="block text-xs font-medium text-ink-muted">Installment {index + 1} condition {conditionIndex + 1}<textarea className="paper-input mt-1" rows={3} value={condition} required onChange={event => setItem(index, { conditions: item.conditions.map((text, position) => position === conditionIndex ? event.target.value : text) })} /></label>{!disabled && <button type="button" className="paper-secondary" onClick={() => setItem(index, { conditions: item.conditions.filter((_, position) => position !== conditionIndex) })}>Remove condition {conditionIndex + 1}</button>}</div>)}
          {!disabled && <button type="button" className="paper-secondary" onClick={() => setItem(index, { conditions: [...(item.conditions || []), ''] })}>Add condition to installment {index + 1}</button>}
        </div>)}
        {!disabled && <button type="button" className="paper-secondary" onClick={addItem}>Add cash installment</button>}
      </div>}
      {!policy ? <div className="space-y-2"><p className="text-sm text-ink-muted">No reviewed withholding policy. Withholding is distinct from VAT.</p>{!disabled && <button type="button" className="paper-secondary" onClick={() => onChange({ ...terms, withholding_policy: { policy_id: '', version: '1', rate: '', rounding_mode: '', decimal_places: null, source_reference: '' } })}>Add withholding policy</button>}</div> : <div className="space-y-3 border-t border-surface-border pt-4">
        <div className="flex flex-wrap items-center justify-between gap-2"><h4 className="text-sm font-semibold">Withholding policy</h4>{!disabled && <button type="button" className="paper-secondary" onClick={() => onChange({ ...terms, withholding_policy: null })}>Remove withholding policy</button>}</div>
        <details className="paper-disclosure rounded-lg bg-surface-muted p-3" open={!policy.policy_id || !policy.source_reference || undefined}><summary className="text-xs font-medium">Policy version and source reference</summary><div className="mt-3 space-y-3"><div className="grid gap-3 sm:grid-cols-2">
          <Field label="Withholding policy ID" value={policy.policy_id} onChange={value => setRule('withholding_policy', { policy_id: value })} />
          <Field label="Withholding policy version" value={policy.version} onChange={value => setRule('withholding_policy', { version: value })} />
        </div><Field label="Withholding policy source reference" value={policy.source_reference} onChange={value => setRule('withholding_policy', { source_reference: value })} /></div></details>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Withholding rate (fraction, e.g. 0.1 = 10%)" value={policy.rate} inputMode="decimal" onChange={value => setRule('withholding_policy', { rate: value })} />
          <label className="block text-xs font-medium text-ink-muted">Withholding rounding<select className="paper-input mt-1" required value={policy.rounding_mode || ''} onChange={event => setRule('withholding_policy', { rounding_mode: event.target.value })}><option value="">Choose reviewed rounding</option><option value="down">Down (truncate)</option><option value="half_up">Half up</option><option value="half_even">Half even</option></select></label>
          <Field label="Withholding decimal places" type="number" min={0} max={6} step={1} value={policy.decimal_places} onChange={value => setRule('withholding_policy', { decimal_places: value === '' ? null : Number(value) })} />
        </div>
      </div>}
    </fieldset>
    <details className="paper-disclosure"><summary>Advanced payment rule JSON</summary><div className="mt-3"><SchemaFields schema={schema} value={terms} onChange={next => onChange(assertSavedInstallmentIds(next, savedInstallmentIds))} disabled={disabled} only={AGREEMENT_PAYMENT_FIELDS} idPrefix={disabled ? 'payment-rules-read' : 'payment-rules-edit'} /></div></details>
    </div></details>
  </section>
}
