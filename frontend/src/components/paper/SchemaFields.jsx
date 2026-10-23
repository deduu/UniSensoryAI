import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { applyFieldValue, fieldDefinitions, jsonEditorValidity, parseStructuredValue, resolveSchema } from '../../paper/helpers.js'
import Button from '../ui/Button'
import FieldSourceLinks from './FieldSourceLinks'
import CanonicalValue from './CanonicalValue.js'
import { appendPointer, canEditStringList, editStringList, textRows } from './readableFields.js'
import { isMoneyField } from '../../paper/monetaryFields.js'
import MoneyInput from './MoneyInput.jsx'

const inputClass = 'w-full rounded-lg border border-surface-border bg-surface px-3 py-2 text-sm text-ink focus:border-brand focus:ring-brand disabled:bg-surface-muted disabled:opacity-70'

/** Keep invalid controls reachable when a reviewer has collapsed their section. */
export function revealInvalidField(event) {
  let parent = event.target.parentElement
  while (parent) {
    if (parent.tagName === 'DETAILS') parent.open = true
    parent = parent.parentElement
  }
}

function StructuredField({ definition, value, onChange, disabled, id, onPendingChange }) {
  const fallback = definition.nullable ? null : definition.type === 'array' ? [] : {}
  const effectiveValue = value === undefined ? fallback : value
  const control = useRef(null)
  const [text, setText] = useState(() => JSON.stringify(effectiveValue, null, 2))
  const [error, setError] = useState('')
  const validity = jsonEditorValidity(text, effectiveValue, error)
  useEffect(() => {
    setText(JSON.stringify(value === undefined ? (definition.nullable ? null : definition.type === 'array' ? [] : {}) : value, null, 2))
    setError('')
  }, [value, definition.type, definition.nullable])

  useEffect(() => { control.current?.setCustomValidity(disabled ? '' : validity) }, [disabled, validity])
  useEffect(() => { onPendingChange?.(Boolean(validity)) }, [onPendingChange, validity])

  function apply() {
    try {
      const parsed = parseStructuredValue(text, definition)
      onChange(parsed)
      setError('')
    } catch (failure) {
      setError(failure instanceof SyntaxError ? 'Enter valid JSON before applying this field.' : failure.message)
    }
  }

  return (
    <div className="space-y-2">
      <textarea
        ref={control} id={id} className={`${inputClass} font-mono text-xs`} rows={4}
        value={text} onChange={event => { setText(event.target.value); setError('') }}
        disabled={disabled} spellCheck={false} aria-invalid={Boolean(error)}
        onInvalid={revealInvalidField}
        aria-describedby={`${id}-help${error ? ` ${id}-error` : ''}`}
      />
      {!disabled && <p id={`${id}-help`} className="text-xs text-ink-muted">Apply JSON to update this field before saving.</p>}
      {error && <p id={`${id}-error`} role="alert" className="text-xs text-red-600 dark:text-red-400">{error}</p>}
      {!disabled && validity && !error && <p role="status" className="text-xs font-medium text-amber-700 dark:text-amber-400">Unapplied JSON edits.</p>}
      {!disabled && <div className="flex flex-wrap gap-2">
        <Button type="button" variant="secondary" className="!px-3 !py-1.5 text-xs" onClick={apply}>Apply {definition.label.toLowerCase()}</Button>
        {definition.nullable && <Button type="button" variant="ghost" className="!px-3 !py-1.5 text-xs" onClick={() => { onChange(null); setText('null'); setError('') }}>Set {definition.label.toLowerCase()} unknown</Button>}
        {validity && <Button type="button" variant="ghost" className="!px-3 !py-1.5 text-xs" onClick={() => { setText(JSON.stringify(effectiveValue, null, 2)); setError('') }}>Discard edits</Button>}
      </div>}
    </div>
  )
}

/** Edit source clauses directly while retaining an explicit advanced JSON alternative. */
function StringListField({ definition, value, onChange, disabled, id, fieldPath }) {
  const [pending, setPending] = useState(false)
  const items = Array.isArray(value) ? value : []
  const locked = disabled || pending
  const update = action => onChange(editStringList(value, action))
  return <div className="paper-clause-editor space-y-3">
    {value == null && <p className="text-sm italic text-ink-faint">Unknown / not provided</p>}
    {Array.isArray(value) && !items.length && <p className="text-sm text-ink-muted">No clauses. This is an empty list, rather than unknown.</p>}
    {items.map((text, index) => <div key={index} data-review-field={appendPointer(fieldPath, index)} className="paper-clause-editor-item">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <label htmlFor={`${id}-${index}`} className="text-xs font-medium text-ink-muted">Clause {index + 1}</label>
        <FieldSourceLinks fieldPath={appendPointer(fieldPath, index)} label={`${definition.label.toLowerCase()}, clause ${index + 1}`} />
      </div>
      <textarea id={`${id}-${index}`} className={`${inputClass} paper-clause-input`} value={text} rows={textRows(text)} disabled={locked}
        onChange={event => update({ type: 'replace', index, text: event.target.value })} onInvalid={revealInvalidField} />
      <Button type="button" variant="ghost" className="mt-1 !px-2 !py-1 text-xs" disabled={locked} onClick={() => update({ type: 'remove', index })}>Remove clause {index + 1}</Button>
    </div>)}
    <div className="flex flex-wrap gap-2">
      <Button type="button" variant="secondary" className="!px-3 !py-1.5 text-xs" disabled={locked} onClick={() => update({ type: 'append' })}>Add clause</Button>
      {definition.nullable && <Button type="button" variant="ghost" className="!px-3 !py-1.5 text-xs" disabled={locked || value == null} onClick={() => onChange(null)}>Set unknown</Button>}
      {value == null && <Button type="button" variant="ghost" className="!px-3 !py-1.5 text-xs" disabled={locked} onClick={() => onChange([])}>Set empty list</Button>}
    </div>
    <details className="paper-disclosure">
      <summary className="text-xs">Advanced JSON editor</summary>
      <div className="mt-3"><StructuredField definition={definition} value={value} onChange={onChange} disabled={disabled} id={`${id}-json`} onPendingChange={setPending} /></div>
    </details>
    {pending && <p className="text-xs text-amber-700 dark:text-amber-400">Apply or discard the JSON edits before editing clauses or saving.</p>}
  </div>
}

/** Render the server's schema, preserving strings, nulls, and extension objects. */
export function SchemaFields({ schema, value = {}, onChange, disabled = false, idPrefix, exclude = [], only, requirements = [], requiredFields = [] }) {
  const generatedId = useId()
  const prefix = idPrefix || generatedId
  const fields = useMemo(() => fieldDefinitions(schema), [schema])
  const [errors, setErrors] = useState({})

  useEffect(() => { setErrors({}) }, [schema])

  function change(field, raw) {
    try {
      onChange(applyFieldValue(value, field.name, raw, field))
      setErrors(current => ({ ...current, [field.name]: '' }))
    } catch (error) {
      setErrors(current => ({ ...current, [field.name]: error.message }))
    }
  }

  if (!fields.length) return <p className="text-sm text-ink-muted">Field schema is unavailable. Reload the workspace to fetch its schema.</p>

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
      {fields.filter(field => !exclude.includes(field.name) && (!only || only.includes(field.name))).map(field => {
        const id = `${prefix}-${field.name}`
        const current = value[field.name]
        const structured = field.type === 'object' || field.type === 'array'
        const longText = !field.enum && field.type === 'string' && field.maxLength > 1000 && !field.format
        const fieldPath = appendPointer('', field.name)
        const listDefinition = { ...field, items: resolveSchema(field.items, schema?.json_schema || schema) }
        const descriptionId = `${id}-description`
        const common = {
          id, disabled, className: inputClass, onInvalid: revealInvalidField,
          'aria-describedby': `${field.description ? descriptionId : ''}${errors[field.name] ? ` ${id}-error` : ''}`.trim() || undefined,
          'aria-invalid': Boolean(errors[field.name]),
        }
        const requirement = requirements.find(item => item.field === field.name)?.requirement || (requiredFields.includes(field.name) ? 'required' : 'optional')
        return (
          <div key={field.name} data-review-field={fieldPath} className={`min-w-0 ${disabled ? 'paper-readonly-field' : ''} ${structured || longText ? 'md:col-span-2' : ''}`}>
            <div className="mb-1.5 flex flex-wrap items-start justify-between gap-2"><div className="flex flex-wrap items-center gap-2">{disabled ? <p id={`${id}-label`} className="text-xs font-medium text-ink-muted">{field.label}</p> : <label htmlFor={id} className="text-xs font-medium text-ink-muted">{field.label}</label>}{(requirements.length > 0 || requiredFields.length > 0) && <span className="text-[10px] capitalize text-ink-faint">{requirement}</span>}</div><FieldSourceLinks fieldPath={fieldPath} label={field.label.toLowerCase()} /></div>
            {disabled ? <div aria-labelledby={`${id}-label`} className="paper-field-value"><CanonicalValue value={current} currency={value.currency} formatted={longText} fieldPath={fieldPath} renderSourceLinks={(path, label) => <FieldSourceLinks fieldPath={path} label={`${field.label.toLowerCase()}, ${label}`} />} /></div> : isMoneyField(fieldPath) ? (
              <MoneyInput {...common} value={current ?? ''} currency={value.currency} onChange={raw => change(field, raw)} />
            ) : structured && canEditStringList(listDefinition, current) ? (
              <StringListField definition={listDefinition} value={current} disabled={disabled} id={id} fieldPath={fieldPath} onChange={parsed => onChange({ ...value, [field.name]: parsed })} />
            ) : structured ? (
              <StructuredField definition={field} value={current} disabled={disabled} id={id} onChange={parsed => onChange({ ...value, [field.name]: parsed })} />
            ) : field.enum ? (
              <select {...common} value={current ?? ''} onChange={event => change(field, event.target.value)}>
                <option value="">Unknown / not provided</option>
                {field.enum.filter(option => option !== null).map(option => <option key={String(option)} value={option}>{String(option).replaceAll('_', ' ')}</option>)}
              </select>
            ) : field.type === 'boolean' ? (
              <select {...common} value={current === null || current === undefined ? '' : String(current)} onChange={event => onChange({ ...value, [field.name]: event.target.value === '' ? null : event.target.value === 'true' })}>
                <option value="">Unknown / not provided</option><option value="true">Yes</option><option value="false">No</option>
              </select>
            ) : longText ? (
              <textarea {...common} className={`${inputClass} paper-clause-input`} rows={textRows(current)} value={current ?? ''} maxLength={field.maxLength} onChange={event => change(field, event.target.value)} />
            ) : (
              <input
                {...common} value={current ?? ''} maxLength={field.maxLength}
                type={field.format === 'date' ? 'date' : ['integer', 'number'].includes(field.type) ? 'number' : 'text'}
                step={field.type === 'integer' ? 1 : field.type === 'number' ? 'any' : undefined}
                inputMode={field.pattern?.includes('[0-9]') ? 'decimal' : undefined}
                onChange={event => change(field, event.target.value)}
              />
            )}
            {field.description && <details className="mt-1 text-xs text-ink-muted"><summary aria-label={`Guidance for ${field.label.toLowerCase()}`} className="cursor-pointer text-ink-faint">Field guidance</summary><p id={descriptionId} className="mt-2 leading-relaxed">{field.description}</p></details>}
            {errors[field.name] && <p id={`${id}-error`} role="alert" className="mt-1 text-xs text-red-600 dark:text-red-400">{errors[field.name]}</p>}
          </div>
        )
      })}
    </div>
  )
}

export default SchemaFields
