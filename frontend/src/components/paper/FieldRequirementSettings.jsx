import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { formatError } from '../../paper/helpers.js'
import {
  MATCH_DOCUMENT_TYPES, requirementFields, createRequirementDraft, updateFieldRequirement,
  updateRequirementCondition, serializeRequirementOverrides, requirementUsesHostDefault, requirementDraftChanged,
} from '../../paper/fieldRequirements.js'
import './fieldRequirementSettings.css'

function ConditionValue({ definition, value, label, id, disabled, onChange }) {
  const choices = definition?.enum?.filter(choice => choice !== null)
  if (choices) return <select id={id} aria-label={`Condition value for ${label}`} className="paper-input" disabled={disabled} value={choices.findIndex(choice => Object.is(choice, value))} onChange={event => onChange(choices[Number(event.target.value)])} required>
    <option value={-1} disabled>Choose a value</option>
    {choices.map((choice, index) => <option key={index} value={index}>{String(choice)}</option>)}
  </select>
  if (definition?.type === 'boolean') return <select id={id} aria-label={`Condition value for ${label}`} className="paper-input" disabled={disabled} value={String(value)} onChange={event => onChange(event.target.value === 'true')}><option value="true">True</option><option value="false">False</option></select>
  const numeric = ['integer', 'number'].includes(definition?.type)
  return <input id={id} aria-label={`Condition value for ${label}`} className="paper-input" disabled={disabled}
    type={numeric ? 'number' : definition?.format === 'date' ? 'date' : 'text'}
    step={definition?.type === 'integer' ? 1 : numeric ? 'any' : undefined}
    min={numeric ? definition?.minimum : undefined} max={numeric ? definition?.maximum : undefined}
    minLength={!numeric ? definition?.minLength : undefined} maxLength={!numeric ? definition?.maxLength || 4000 : undefined}
    value={value ?? ''} required={numeric || Boolean(definition?.minLength)}
    onChange={event => onChange(event.target.value)} />
}

function RequirementRow({ row, definition, schemas, disabled, inherited, id, onChange, onCondition }) {
  const label = definition.label
  const when = row.when
  const conditionFields = requirementFields(schemas, when?.role)
  const conditionDefinition = conditionFields.find(field => field.name === when?.field)
  return <article className="paper-requirement-row">
    <div className="paper-requirement-heading">
      <div className="min-w-0"><label htmlFor={`${id}-mode`} className="font-medium text-sm text-ink">{label}</label><code className="mt-0.5 block text-[11px] text-ink-faint">{row.field}</code></div>
      <select id={`${id}-mode`} className="paper-input" aria-label={`Requirement for ${label}`} disabled={disabled} value={row.requirement} onChange={event => onChange(row, { requirement: event.target.value })}>
        <option value="required">Required</option><option value="optional">Optional</option><option value="conditional">Conditional</option>
      </select>
    </div>
    {definition.description && <details className="paper-disclosure paper-requirement-help"><summary>Field guidance</summary><p className="mt-2 text-xs text-ink-muted">{definition.description}</p></details>}
    {row.requirement === 'conditional' && <fieldset className="paper-requirement-condition" disabled={disabled}>
      <legend className="text-xs font-medium text-ink-muted">Required when</legend>
      <div><label htmlFor={`${id}-role`}>Document type</label><select id={`${id}-role`} className="paper-input" value={when?.role || ''} aria-label={`Condition document type for ${label}`} onChange={event => onCondition(row, { role: event.target.value })}>{MATCH_DOCUMENT_TYPES.map(item => <option key={item.role} value={item.role}>{item.label}</option>)}</select></div>
      <div><label htmlFor={`${id}-field`}>Field</label><select id={`${id}-field`} className="paper-input" value={when?.field || ''} aria-label={`Condition field for ${label}`} onChange={event => onCondition(row, { field: event.target.value })} required>{conditionFields.map(field => <option key={field.name} value={field.name}>{field.label}</option>)}</select></div>
      <div><label htmlFor={`${id}-operator`}>Condition</label><select id={`${id}-operator`} className="paper-input" value={when?.operator || 'present'} aria-label={`Condition operator for ${label}`} onChange={event => onCondition(row, { operator: event.target.value })}><option value="present">Is present</option><option value="absent">Is absent</option><option value="equals">Equals</option></select></div>
      {when?.operator === 'equals' && <div><label htmlFor={`${id}-value`}>Value</label><ConditionValue definition={conditionDefinition} value={when.value} label={label} id={`${id}-value`} disabled={disabled} onChange={value => onCondition(row, { value })} /></div>}
      <p className="paper-requirement-condition-note">The condition uses source fields from the selected case documents. Use “is absent” for a missing or unknown value.</p>
    </fieldset>}
    <details className="paper-disclosure paper-requirement-help">
      <summary>Requirement explanation</summary>
      <label htmlFor={`${id}-reason`} className="mt-2 block text-xs text-ink-muted">Shown in Document Match</label>
      <textarea id={`${id}-reason`} aria-label={`Requirement explanation for ${label}`} className="paper-input mt-1" disabled={disabled || inherited} rows={2} maxLength={4000} value={row.reason || ''} onChange={event => onChange(row, { reason: event.target.value })} />
      <p className="mt-1 text-xs text-ink-faint">{inherited ? 'Using the host default. Change the requirement or condition to customize its explanation.' : 'Leave blank to use the standard explanation.'}</p>
    </details>
  </article>
}

/** Present one shared field policy with a bounded, searchable document-type editor. */
export function FieldRequirementEditor({ schemas = [], policy, draft = [], role = 'rent_invoice', search = '', dirty = false, usingDeploymentDefaults = false, busy = false, loading = false, error = '', conflict = false, reloadPending = false, savedMessage = '', onRoleChange, onSearchChange, onChange, onCondition, onSave, onRefresh, onDiscard, onReloadLatest, onCancelReload, onUseDeploymentDefaults }) {
  const id = useId()
  const fields = requirementFields(schemas, role)
  const definitions = new Map(fields.map(field => [field.name, field]))
  const query = search.toLowerCase().trim()
  const rows = draft.filter(row => row.role === role && definitions.has(row.field) && (!query || `${row.field} ${definitions.get(row.field).label}`.toLowerCase().includes(query)))
  const editable = policy?.can_edit === true
  const hasCatalog = MATCH_DOCUMENT_TYPES.every(item => requirementFields(schemas, item.role).length > 0)
  const locked = !editable || busy || loading
  const editingPolicy = usingDeploymentDefaults ? { ...policy, overrides: [] } : policy
  const counts = draft.filter(row => row.role === role).reduce((result, row) => ({ ...result, [row.requirement]: (result[row.requirement] || 0) + 1 }), {})
  return <section className="paper-panel paper-requirement-settings" aria-labelledby={`${id}-title`} aria-busy={loading || busy}>
    <div className="paper-requirement-top">
      <div><h2 id={`${id}-title`} className="text-lg font-semibold text-ink">Field requirements</h2><p className="mt-1 text-sm text-ink-muted">Choose the required, optional and conditional fields for each document type in Document Match.</p></div>
      <button type="button" className="paper-secondary" disabled={busy || loading} onClick={onRefresh}>Refresh settings</button>
    </div>
    <p className="paper-notice text-xs">Shared settings apply to future readiness checks and reconciliations. Saved results retain the policy used at assessment. Accounting and approval checks still apply.</p>
    {policy && <details className="paper-disclosure paper-requirement-metadata"><summary>Policy revision {policy.revision} · {policy.policy_id}</summary><dl className="mt-2 grid gap-1 text-xs text-ink-muted"><dt>Policy version</dt><dd className="font-mono">{policy.policy_version}</dd>{policy.updated_by && <><dt>Updated by</dt><dd>{policy.updated_by}</dd></>}{policy.updated_at && <><dt>Updated at</dt><dd>{new Date(policy.updated_at).toLocaleString()}</dd></>}</dl></details>}
    {policy && !editable && <p role="status" className="paper-notice">These settings are read-only for your account. An authorized AP reviewer can update field requirements.</p>}
    {loading && <p role="status" className="text-sm text-ink-muted">Loading field requirements…</p>}
    {error && <p role="alert" className="paper-error">{error}</p>}
    {conflict && <p role="status" className="paper-notice">Another user saved a newer policy. Your edits are retained. Load the latest settings before editing and saving again.</p>}
    {reloadPending && <div className="paper-notice"><p>You have unsaved field requirements. Discard these changes to load the latest shared settings.</p><div className="mt-2 flex flex-wrap gap-2"><button type="button" className="paper-secondary" disabled={busy || loading} onClick={onReloadLatest}>Discard changes and reload</button><button type="button" className="paper-secondary" onClick={onCancelReload}>Keep editing</button></div></div>}
    {savedMessage && <p role="status" className="text-sm text-brand">{savedMessage}</p>}
    {usingDeploymentDefaults && <p role="status" className="paper-notice">Deployment defaults are staged for all document types. Save field requirements to remove the existing overrides, or discard edits to keep the saved policy. Further edits will be saved as new overrides.</p>}
    {policy && <form onSubmit={onSave}>
      <div className="paper-requirement-filters">
        <div><label htmlFor={`${id}-document`} className="text-xs font-medium text-ink-muted">Document type</label><select id={`${id}-document`} className="paper-input mt-1" value={role} onChange={event => onRoleChange?.(event.target.value)}>{MATCH_DOCUMENT_TYPES.map(item => <option key={item.role} value={item.role}>{item.label}</option>)}</select></div>
        <div><label htmlFor={`${id}-search`} className="text-xs font-medium text-ink-muted">Find a field</label><input id={`${id}-search`} className="paper-input mt-1" type="search" placeholder="Search field names" value={search} onChange={event => onSearchChange?.(event.target.value)} /></div>
      </div>
      <p className="mb-3 text-xs text-ink-muted">{counts.required || 0} required · {counts.conditional || 0} conditional · {counts.optional || 0} optional</p>
      {!hasCatalog && <p role="status" className="paper-notice mb-3">Document field definitions are unavailable. Refresh the page to load the schemas before changing settings.</p>}
      <div className="paper-requirement-list">{rows.map(row => <RequirementRow key={`${row.role}:${row.field}`} row={row} definition={definitions.get(row.field)} schemas={schemas} disabled={locked} inherited={requirementUsesHostDefault(row, schemas, editingPolicy)} id={`${id}-${row.role}-${row.field}`} onChange={onChange} onCondition={onCondition} />)}</div>
      {!rows.length && hasCatalog && <p className="py-6 text-sm text-ink-muted">No fields match this search.</p>}
      <div className="paper-requirement-actions"><span role="status" className="text-xs text-ink-muted">{dirty ? 'Unsaved changes across document types' : 'Settings are up to date'}</span><div className="flex flex-wrap gap-2"><button type="button" className="paper-secondary" disabled={locked || !hasCatalog || !Array.isArray(policy.base_requirements) || (!(policy.overrides?.length) && !dirty)} onClick={onUseDeploymentDefaults}>Use deployment defaults</button><button type="button" className="paper-secondary" disabled={!dirty || locked} onClick={onDiscard}>Discard edits</button><button type="submit" className="paper-primary" disabled={!dirty || locked || !hasCatalog || conflict}>{busy ? 'Saving…' : 'Save field requirements'}</button></div></div>
    </form>}
  </section>
}

/** Persist shared settings with optimistic concurrency and explicit draft disposal. */
export default function FieldRequirementSettings({ api, schemas = [], onSaved }) {
  const [policy, setPolicy] = useState(null)
  const [draft, setDraft] = useState([])
  const [role, setRole] = useState('rent_invoice')
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [conflict, setConflict] = useState(false)
  const [reloadPending, setReloadPending] = useState(false)
  const [savedMessage, setSavedMessage] = useState('')
  const [usingDeploymentDefaults, setUsingDeploymentDefaults] = useState(false)
  const session = useRef(null)
  const latestSchemas = useRef(schemas)
  latestSchemas.current = schemas
  const base = useMemo(() => createRequirementDraft(policy, schemas), [policy, schemas])
  const dirty = usingDeploymentDefaults || requirementDraftChanged(base, draft)

  useEffect(() => {
    const current = { active: true, busy: true }
    session.current = current
    setPolicy(null); setDraft([]); setLoading(true); setBusy(false); setError(''); setConflict(false); setReloadPending(false); setSavedMessage(''); setUsingDeploymentDefaults(false)
    api.fieldRequirements().then(data => {
      if (!current.active) return
      setPolicy(data); setDraft(createRequirementDraft(data, latestSchemas.current))
    }).catch(failure => { if (current.active) setError(formatError(failure)) }).finally(() => {
      current.busy = false
      if (current.active) setLoading(false)
    })
    return () => { current.active = false }
  }, [api])

  useEffect(() => {
    if (policy && schemas.length) setDraft(current => createRequirementDraft({ requirements: [...(usingDeploymentDefaults ? policy.base_requirements : policy.requirements), ...current] }, schemas))
  }, [policy, schemas, usingDeploymentDefaults])

  async function reload() {
    const current = session.current
    if (!current?.active || current.busy) return
    current.busy = true; setLoading(true); setError(''); setSavedMessage('')
    try {
      const data = await api.fieldRequirements()
      if (!current.active) return
      setPolicy(data); setDraft(createRequirementDraft(data, latestSchemas.current)); setConflict(false); setReloadPending(false); setUsingDeploymentDefaults(false)
    } catch (failure) { if (current.active) setError(formatError(failure)) }
    finally { current.busy = false; if (current.active) setLoading(false) }
  }

  function change(row, patch, condition = false) {
    if (!policy?.can_edit || session.current?.busy) return
    setDraft(current => (condition ? updateRequirementCondition : updateFieldRequirement)(current, row.role, row.field, patch, schemas))
    setSavedMessage('')
  }

  async function save(event) {
    event?.preventDefault()
    const current = session.current
    if (!current?.active || current.busy || !policy?.can_edit || !dirty || conflict) return
    let requirements
    try { requirements = serializeRequirementOverrides(draft, schemas, usingDeploymentDefaults ? { ...policy, overrides: [] } : policy) }
    catch (failure) { setError(failure.message); return }
    current.busy = true; setBusy(true); setError(''); setSavedMessage('')
    try {
      const data = await api.saveFieldRequirements({ expected_revision: policy.revision, requirements })
      if (!current.active) return
      setPolicy(data); setDraft(createRequirementDraft(data, latestSchemas.current)); setConflict(false); setReloadPending(false); setUsingDeploymentDefaults(false)
      setSavedMessage('Field requirements saved. Document Match will use this policy on the next readiness check or reconciliation.')
      onSaved?.(data)
    } catch (failure) {
      if (!current.active) return
      setError(formatError(failure))
      if (failure.status === 409) setConflict(true)
      if (failure.status === 403) setPolicy(previous => ({ ...previous, can_edit: false }))
    } finally { current.busy = false; if (current.active) setBusy(false) }
  }

  return <FieldRequirementEditor schemas={schemas} policy={policy} draft={draft} role={role} search={search} dirty={Boolean(policy) && dirty} usingDeploymentDefaults={usingDeploymentDefaults} busy={busy} loading={loading} error={error} conflict={conflict} reloadPending={reloadPending} savedMessage={savedMessage}
    onRoleChange={setRole} onSearchChange={setSearch} onChange={(row, patch) => change(row, patch)} onCondition={(row, patch) => change(row, patch, true)} onSave={save}
    onRefresh={() => dirty && policy ? setReloadPending(true) : reload()}
    onDiscard={() => { setDraft(base); setUsingDeploymentDefaults(false); setError(''); setSavedMessage(''); setReloadPending(false) }}
    onUseDeploymentDefaults={() => {
      if (!policy?.can_edit || session.current?.busy || !Array.isArray(policy.base_requirements)) return
      setDraft(createRequirementDraft({ requirements: policy.base_requirements }, schemas)); setUsingDeploymentDefaults(true); setError(''); setSavedMessage(''); setReloadPending(false)
    }}
    onReloadLatest={reload} onCancelReload={() => setReloadPending(false)} />
}
