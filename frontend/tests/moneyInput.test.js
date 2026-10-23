import test from 'node:test'
import assert from 'node:assert/strict'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'
import vm from 'node:vm'
import { build } from 'esbuild'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'

async function compiledInput() {
  const component = new URL('../src/components/paper/MoneyInput.jsx', import.meta.url)
  const built = await build({ entryPoints: [fileURLToPath(component)], bundle: true, write: false, platform: 'node', format: 'cjs', jsx: 'automatic', packages: 'external' })
  return { code: built.outputFiles[0].text, require: createRequire(component) }
}

test('MoneyInput compiles and renders localized exact strings with ordinary input attributes', async () => {
  const compiled = await compiledInput()
  const module = { exports: {} }
  vm.runInNewContext(compiled.code, { module, exports: module.exports, require: compiled.require })
  const MoneyInput = module.exports.default
  const render = props => renderToStaticMarkup(React.createElement(MoneyInput, { onChange: () => {}, ...props }))
  const html = render({ value: '9007199254740993.00100', currency: 'IDR', name: 'rent', id: 'rent', required: true, className: 'paper-input', 'aria-describedby': 'rent-description' })
  assert.match(html, /value="9\.007\.199\.254\.740\.993,00100"/)
  assert.match(html, /type="text"/)
  assert.match(html, /inputMode="decimal"/)
  assert.match(html, /name="rent"/)
  assert.match(html, /required=""/)
  assert.match(html, /rent-description/)
  assert.match(render({ value: '0.0000', currency: 'USD' }), /value="0\.0000"/)
  assert.match(render({ value: '', currency: 'IDR' }), /value=""/)
  assert.match(render({ value: '1e3', currency: 'IDR' }), /value="1e3"/)
})

// Exercise the actual handlers/effects with a small deterministic hook runner;
// native constraint messages are captured on the attached input control.
async function inputHarness(initial) {
  const compiled = await compiledInput()
  const slots = []
  let cursor = 0
  let pending = []
  let dirty = false
  let props = initial
  let input
  let tree
  const node = { message: '', setCustomValidity(message) { this.message = message } }
  const hooks = {
    forwardRef: component => component,
    useId: () => { cursor += 1; return 'money-test' },
    useRef: initialValue => { const index = cursor++; slots[index] ??= { current: initialValue }; return slots[index] },
    useState: initialValue => {
      const index = cursor++
      if (!(index in slots)) slots[index] = typeof initialValue === 'function' ? initialValue() : initialValue
      return [slots[index], value => {
        const next = typeof value === 'function' ? value(slots[index]) : value
        if (!Object.is(next, slots[index])) { slots[index] = next; dirty = true }
      }]
    },
    useCallback: callback => { cursor += 1; return callback },
    useEffect: (effect, dependencies) => {
      const index = cursor++
      if (!dependencies || !slots[index] || dependencies.some((value, position) => !Object.is(value, slots[index][position]))) pending.push(effect)
      slots[index] = dependencies
    },
  }
  const module = { exports: {} }
  vm.runInNewContext(compiled.code, { module, exports: module.exports, require: name => name === 'react' ? hooks : compiled.require(name) })
  const render = () => {
    for (let pass = 0; pass < 12; pass += 1) {
      dirty = false; cursor = 0; pending = []
      tree = module.exports.default(props, null)
      input = tree.props.children[0]
      input.ref(node)
      pending.forEach(effect => effect())
      if (!dirty) return
    }
    throw new Error('Money input did not settle after external update')
  }
  render()
  return {
    get value() { return input.props.value },
    get message() { return node.message },
    get tree() { return tree },
    update(changes) { props = { ...props, ...changes }; render() },
    event(name, value = input.props.value) { input.props[name]({ target: { ...node, value, setCustomValidity: message => node.setCustomValidity(message) } }); render() },
  }
}

test('focus preserves displayed text and typing or grouped paste emits an exact canonical value', async () => {
  const calls = []
  const input = await inputHarness({ value: '1234.50', currency: 'IDR', onChange: value => { calls.push(value); input.update({ value }) } })
  input.event('onFocus')
  assert.equal(input.value, '1.234,50')
  assert.deepEqual(calls, [])
  input.event('onChange', '12345,5000')
  assert.equal(input.value, '12345,5000')
  assert.deepEqual(calls, ['12345.5000'])
  assert.equal(input.message, '')
  input.event('onChange', '-9.007.199.254.740.993,000100')
  assert.deepEqual(calls, ['12345.5000', '-9007199254740993.000100'])
  input.event('onBlur')
  assert.equal(input.value, '-9.007.199.254.740.993,000100')
})

test('repeated focus never rewrites selected text or reapplies a value', async () => {
  const calls = []
  const input = await inputHarness({ value: '9007199254740993.00100', currency: 'IDR', onChange: value => calls.push(value) })
  const original = input.value
  input.event('onFocus')
  assert.equal(input.value, original)
  input.event('onFocus')
  assert.equal(input.value, original)
  input.event('onBlur')
  input.event('onFocus')
  assert.equal(input.value, original)
  assert.deepEqual(calls, [])
})

test('incomplete and unapplied edits set native constraint messages and preserve host data', async () => {
  const calls = []
  const input = await inputHarness({ value: '1234.50', currency: 'IDR', onChange: value => calls.push(value) })
  input.event('onChange', '1.234,')
  assert.equal(input.value, '1.234,')
  assert.match(input.message, /complete amount/)
  assert.deepEqual(calls, [])
  input.event('onBlur')
  assert.equal(input.value, '1.234,')
  input.event('onChange', '2000,00')
  assert.deepEqual(calls, ['2000.00'])
  assert.match(input.message, /update to apply/)
  input.update({ value: '2000.00' })
  assert.equal(input.message, '')
  input.event('onBlur')
  assert.equal(input.value, '2.000,00')
})

test('external updates and currency changes reset safely without emitting a changed amount', async () => {
  const calls = []
  const input = await inputHarness({ value: '1234.50', currency: 'IDR', onChange: value => calls.push(value) })
  input.event('onChange', 'invalid')
  input.update({ value: '9007199254740993.0000' })
  assert.equal(input.value, '9.007.199.254.740.993,0000')
  assert.equal(input.message, '')
  input.update({ currency: 'USD' })
  assert.equal(input.value, '9,007,199,254,740,993.0000')
  assert.equal(input.message, '')
  assert.deepEqual(calls, [])
  input.event('onChange', 'invalid')
  input.update({ disabled: true })
  assert.equal(input.message, '')
})

test('read-only fields retain grouped presentation on focus', async () => {
  const input = await inputHarness({ value: '1234.00', currency: 'IDR', readOnly: true, onChange: () => assert.fail('read-only input emitted a change') })
  input.event('onFocus')
  assert.equal(input.value, '1.234,00')
})
