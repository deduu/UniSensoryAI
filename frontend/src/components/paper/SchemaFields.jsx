import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { applyFieldValue, fieldDefinitions, jsonEditorValidity, parseStructuredValue } from '../../paper/helpers.js'
import Button from '../ui/Button'
import FieldSourceLinks from './FieldSourceLinks'

const inputClass = 'w-full rounded-lg border border-surface-border bg-surface px-3 py-2 text-sm text-ink focus:border-brand focus:ring-brand disabled:bg-surface-muted disabled:opacity-70'

/** Keep invalid controls reachable when a reviewer has collapsed their section. */
export function revealInvalidField(event) {
  let parent = event.target.parentElement
  while (parent) {
    if (parent.tagName === 'DETAILS') parent.open = true
    parent = parent.parentElement
  }
}

function StructuredField({ definition, value, onChange, disabled, id }) {
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

/** Render the server's schema, preserving strings, nulls, and extension objects. */
export function SchemaFields({ schema, value = {}, onChange, disabled = false, idPrefix, exclude = [], only }) {
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
        const descriptionId = `${id}-description`
        const common = {
          id, disabled, className: inputClass, onInvalid: revealInvalidField,
          'aria-describedby': `${field.description ? descriptionId : ''}${errors[field.name] ? ` ${id}-error` : ''}`.trim() || undefined,
          'aria-invalid': Boolean(errors[field.name]),
        }
        return (
          <div key={field.name} data-review-field={`/${field.name.replaceAll('~', '~0').replaceAll('/', '~1')}`} className={`min-w-0 ${structured || longText ? 'md:col-span-2' : ''}`}>
            <div className="mb-1.5 flex flex-wrap items-start justify-between gap-2"><label htmlFor={id} className="text-xs font-medium text-ink-muted">{field.label}</label><FieldSourceLinks fieldPath={`/${field.name.replaceAll('~', '~0').replaceAll('/', '~1')}`} label={field.label.toLowerCase()} /></div>
            {structured ? (
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
              <textarea {...common} rows={2} value={current ?? ''} maxLength={field.maxLength} onChange={event => change(field, event.target.value)} />
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
