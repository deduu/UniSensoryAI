import { useEffect, useId, useRef, useState } from 'react'
import { jsonEditorValidity, parseImport } from '../../paper/helpers.js'
import Button from '../ui/Button'

/** Explicit JSON apply boundary: editing the textarea never saves a record. */
export function JsonImport({
  value, onImport, label = 'Import JSON', helpText, kind = 'object',
  currentIdentity, disabled = false, open = false,
}) {
  const id = useId()
  const control = useRef(null)
  const [text, setText] = useState(() => JSON.stringify(value ?? {}, null, 2))
  const [error, setError] = useState('')
  const [applied, setApplied] = useState(false)
  const validity = jsonEditorValidity(text, value, error)

  useEffect(() => {
    setText(JSON.stringify(value ?? {}, null, 2))
    setError('')
    setApplied(false)
  }, [value])

  useEffect(() => { control.current?.setCustomValidity(disabled ? '' : validity) }, [disabled, validity])

  function discard() {
    setText(JSON.stringify(value ?? {}, null, 2))
    setError('')
    setApplied(false)
  }

  function apply() {
    try {
      const parsed = parseImport(text, kind, currentIdentity)
      onImport(parsed)
      setError('')
      setApplied(true)
    } catch (failure) {
      setError(failure.message || 'Unable to apply this JSON.')
      setApplied(false)
    }
  }

  return (
    <details open={open || undefined} className="rounded-xl border border-surface-border bg-surface-subtle p-4">
      <summary className="cursor-pointer text-sm font-medium text-ink">{label}</summary>
      <div className="mt-3 space-y-3">
        <p id={`${id}-help`} className="text-xs leading-relaxed text-ink-muted">
          {helpText || 'Paste a JSON object, then apply it to the form. Saving the record is a separate action.'}
        </p>
        <label className="sr-only" htmlFor={id}>{label} content</label>
        <textarea
          ref={control} id={id} value={text} disabled={disabled} rows={12} spellCheck={false}
          onChange={event => { setText(event.target.value); setError(''); setApplied(false) }}
          onInvalid={event => event.currentTarget.closest('details')?.setAttribute('open', '')}
          aria-describedby={`${id}-help${error ? ` ${id}-error` : ''}`}
          aria-invalid={Boolean(error)}
          className="w-full resize-y rounded-lg border border-surface-border bg-surface px-3 py-2 font-mono text-xs text-ink focus:border-brand focus:ring-brand disabled:opacity-60"
        />
        {error && <p id={`${id}-error`} role="alert" className="text-sm text-red-600 dark:text-red-400">{error}</p>}
        {!disabled && validity && !error && <p role="status" className="text-xs font-medium text-amber-700 dark:text-amber-400">Unapplied JSON edits. Apply or discard them before saving.</p>}
        {applied && <p role="status" className="text-xs text-emerald-700 dark:text-emerald-400">JSON applied to the form. Save to persist changes.</p>}
        {!disabled && <div className="flex flex-wrap gap-2">
          <Button type="button" variant="secondary" onClick={apply}>Apply JSON to form</Button>
          {validity && <Button type="button" variant="ghost" onClick={discard}>Discard JSON edits</Button>}
        </div>}
      </div>
    </details>
  )
}

export default JsonImport
