import { forwardRef, useCallback, useEffect, useId, useRef, useState } from 'react'
import { formatMoneyAmount, moneyConvention, moneyInputValidity, parseMoneyInput } from '../../paper/money.js'

/** Edit localized amounts while the host retains exact canonical decimal strings. */
export default forwardRef(function MoneyInput({
  value, onChange, currency, onFocus, onBlur, disabled = false, readOnly = false,
  'aria-describedby': describedBy, 'aria-invalid': invalid, ...props
}, forwardedRef) {
  const generatedId = useId()
  const control = useRef(null)
  const convention = moneyConvention(currency)
  const currencyKey = convention.code
  const currentValue = value ?? ''
  const synchronization = useRef({ value: currentValue, currency: currencyKey, emitted: null })
  const [text, setText] = useState(() => formatMoneyAmount(value, currency))
  const [focused, setFocused] = useState(false)
  const validity = moneyInputValidity(text, currentValue, currency)
  const message = disabled || readOnly ? '' : validity
  const hintId = `${generatedId}-money-hint`
  const errorId = `${generatedId}-money-error`
  const descriptions = [describedBy, focused && !readOnly ? hintId : '', message ? errorId : ''].filter(Boolean).join(' ') || undefined

  const bindControl = useCallback(node => {
    control.current = node
    if (typeof forwardedRef === 'function') forwardedRef(node)
    else if (forwardedRef) forwardedRef.current = node
  }, [forwardedRef])

  useEffect(() => {
    const previous = synchronization.current
    const changedCurrency = previous.currency !== currencyKey
    const reflectedEdit = !changedCurrency && previous.emitted === currentValue
    if (changedCurrency || (previous.value !== currentValue && !reflectedEdit)) {
      setText(formatMoneyAmount(value, currency))
    }
    synchronization.current = { value: currentValue, currency: currencyKey, emitted: null }
  }, [value, currency, currentValue, currencyKey])

  // A synchronous parent update can leave the derived message unchanged after
  // the handler set a pending message. Reconcile native validity every render.
  useEffect(() => { control.current?.setCustomValidity(message) })

  function change(event) {
    const next = event.target.value
    setText(next)
    event.target.setCustomValidity(moneyInputValidity(next, currentValue, currency))
    let canonical
    try { canonical = parseMoneyInput(next, currency) } catch {
      // Keep incomplete local text visible without replacing the host's last value.
      return
    }
    synchronization.current.emitted = canonical
    if (canonical !== currentValue) onChange(canonical)
  }

  function focus(event) {
    setFocused(true)
    onFocus?.(event)
  }

  function blur(event) {
    setFocused(false)
    try { setText(formatMoneyAmount(parseMoneyInput(text, currency), currency)) } catch {
      // Invalid text must remain visible and continue to block submission.
    }
    onBlur?.(event)
  }

  return <span className="block min-w-0">
    <input {...props} ref={bindControl} type="text" inputMode="decimal" value={text}
      disabled={disabled} readOnly={readOnly} onChange={change} onFocus={focus} onBlur={blur}
      aria-describedby={descriptions} aria-invalid={Boolean(message) || invalid || undefined} />
    {focused && !readOnly && <span id={hintId} className="mt-1 block text-xs font-normal text-ink-muted">{convention.decimal === ',' ? `${convention.code === 'IDR' ? 'IDR: ' : ''}use a comma for decimals; dots group thousands.` : 'Use a dot for decimals; commas group thousands.'}</span>}
    {message && <span id={errorId} role="status" className="mt-1 block text-xs font-normal text-red-600 dark:text-red-400">{message}</span>}
  </span>
})
