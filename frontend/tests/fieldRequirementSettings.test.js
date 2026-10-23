import test from 'node:test'
import assert from 'node:assert/strict'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'
import vm from 'node:vm'
import { build } from 'esbuild'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'

const schemas = ['rent_invoice', 'tax_invoice', 'utility_statement', 'supporting_document'].map(role => ({ schema_id: `paper.${role}`, json_schema: { properties: { invoice_number: { title: 'Invoice number', type: 'string' }, total: { type: 'string' } } } }))
const initial = { revision: 3, policy_id: 'rent', policy_version: 4, can_edit: true, requirements: [{ role: 'rent_invoice', field: 'invoice_number', requirement: 'required', reason: 'Identify invoice.' }] }
let compiled
async function compile() {
  if (!compiled) {
    const component = new URL('../src/components/paper/FieldRequirementSettings.jsx', import.meta.url)
    const built = await build({ entryPoints: [fileURLToPath(component)], bundle: true, write: false, platform: 'node', format: 'cjs', jsx: 'automatic', packages: 'external', loader: { '.css': 'empty' } })
    compiled = { code: built.outputFiles[0].text, require: createRequire(component) }
  }
  return compiled
}
async function harness(api, extra = {}) {
  const compiled = await compile()
  const slots = []
  let cursor = 0
  let effects = []
  let tree
  let props = { api, schemas, ...extra }
  const hooks = {
    useId: () => { cursor += 1; return 'settings-test' },
    useRef: value => { const index = cursor++; slots[index] ??= { current: value }; return slots[index] },
    useState: value => { const index = cursor++; if (!(index in slots)) slots[index] = typeof value === 'function' ? value() : value; return [slots[index], next => { slots[index] = typeof next === 'function' ? next(slots[index]) : next }] },
    useMemo: callback => { cursor += 1; return callback() },
    useEffect: (effect, dependencies) => { const index = cursor++; const prior = slots[index]; if (!prior || dependencies.some((value, position) => !Object.is(value, prior.dependencies[position]))) { prior?.cleanup?.(); effects.push(() => { const cleanup = effect(); slots[index] = { dependencies, cleanup } }) } },
  }
  const module = { exports: {} }
  vm.runInNewContext(compiled.code, { module, exports: module.exports, require: name => name === 'react' ? hooks : compiled.require(name) })
  const render = () => { cursor = 0; effects = []; tree = module.exports.default(props); effects.forEach(effect => effect()) }
  const settle = async () => { for (let index = 0; index < 5; index += 1) { await Promise.resolve(); render() } }
  render(); await settle()
  return { get editor() { return tree.props }, async act(callback) { await callback(tree.props); await settle() }, async update(next) { props = { ...props, ...next }; render(); await settle() } }
}

test('field settings render readable controls, all document types and conditional fields', async () => {
  const compiled = await compile()
  const module = { exports: {} }
  vm.runInNewContext(compiled.code, { module, exports: module.exports, require: compiled.require })
  const html = renderToStaticMarkup(React.createElement(module.exports.FieldRequirementEditor, {
    schemas, policy: initial, role: 'rent_invoice', search: '', draft: [{ role: 'rent_invoice', field: 'total', requirement: 'conditional', reason: 'Payable when invoiced.', when: { role: 'tax_invoice', field: 'invoice_number', operator: 'equals', value: 'INV-1' } }], dirty: true,
  }))
  assert.match(html, /Field requirements/)
  assert.match(html, /Required/)
  assert.match(html, /Optional/)
  assert.match(html, /Conditional/)
  assert.match(html, /Tax invoice/)
  assert.match(html, /Utility statement/)
  assert.match(html, /Supporting document/)
  assert.match(html, /Condition value for Total/)
  assert.match(html, /Save field requirements/)
  assert.match(html, /Shared settings/)
})

test('readonly settings explain access and disable saving', async () => {
  const compiled = await compile()
  const module = { exports: {} }
  vm.runInNewContext(compiled.code, { module, exports: module.exports, require: compiled.require })
  const html = renderToStaticMarkup(React.createElement(module.exports.FieldRequirementEditor, { schemas, policy: { ...initial, can_edit: false }, role: 'rent_invoice', draft: initial.requirements, dirty: true }))
  assert.match(html, /read.only/i)
  assert.match(html, /authorized AP reviewer/)
  assert.match(html, /disabled=""[^>]*>Save field requirements/)
})

test('server load is stable across rerenders and unsaved type switches retain the draft', async () => {
  let loads = 0
  const api = { fieldRequirements: async () => { loads += 1; return initial } }
  const state = await harness(api)
  assert.equal(state.editor.policy.revision, 3)
  await state.act(editor => editor.onChange({ role: 'rent_invoice', field: 'total' }, { requirement: 'required' }))
  await state.act(editor => editor.onRoleChange('tax_invoice'))
  await state.update({ schemas: [...schemas], onSaved: () => {} })
  assert.equal(loads, 1)
  assert.equal(state.editor.draft.find(row => row.field === 'total' && row.role === 'rent_invoice').requirement, 'required')
  assert.equal(state.editor.dirty, true)
})

test('saving submits expected revision and refresh cannot silently replace edits', async () => {
  let loads = 0
  let submitted
  let saved
  const state = await harness({ fieldRequirements: async () => { loads += 1; return initial }, saveFieldRequirements: async payload => { submitted = payload; return { ...initial, revision: 4, policy_version: 5, requirements: payload.requirements } } }, { onSaved: policy => { saved = policy } })
  await state.act(editor => editor.onChange({ role: 'rent_invoice', field: 'total' }, { requirement: 'required' }))
  await state.act(editor => editor.onRefresh())
  assert.equal(loads, 1)
  assert.equal(state.editor.reloadPending, true)
  await state.act(editor => editor.onCancelReload())
  await state.act(editor => editor.onSave({ preventDefault() {} }))
  assert.equal(submitted.expected_revision, 3)
  assert.equal(submitted.requirements.find(row => row.role === 'rent_invoice' && row.field === 'total').requirement, 'required')
  assert.equal(saved.revision, 4)
  assert.equal(state.editor.dirty, false)
})

test('a stale revision keeps edits and requires explicit discard before loading latest', async () => {
  let loads = 0
  const state = await harness({ fieldRequirements: async () => { loads += 1; return { ...initial, revision: loads === 1 ? 3 : 4 } }, saveFieldRequirements: async () => { throw { status: 409, message: 'Policy changed.' } } })
  await state.act(editor => editor.onChange({ role: 'rent_invoice', field: 'total' }, { requirement: 'required' }))
  await state.act(editor => editor.onSave({ preventDefault() {} }))
  assert.equal(state.editor.conflict, true)
  assert.equal(state.editor.dirty, true)
  assert.equal(state.editor.policy.revision, 3)
  await state.act(editor => editor.onRefresh())
  assert.equal(loads, 1)
  await state.act(editor => editor.onReloadLatest())
  assert.equal(loads, 2)
  assert.equal(state.editor.policy.revision, 4)
  assert.equal(state.editor.dirty, false)
})

test('fetch failures keep settings unavailable and can be retried', async () => {
  let fail = true
  const state = await harness({ fieldRequirements: async () => { if (fail) throw new Error('Unavailable'); return initial } })
  assert.equal(state.editor.policy, null)
  assert.match(state.editor.error, /Unavailable/)
  fail = false
  await state.act(editor => editor.onRefresh())
  assert.equal(state.editor.policy.revision, 3)
})

test('a delayed schema catalog restores the saved requirements without inventing edits', async () => {
  const state = await harness({ fieldRequirements: async () => initial }, { schemas: [] })
  assert.equal(state.editor.draft.length, 0)
  await state.update({ schemas })
  assert.equal(state.editor.draft.find(row => row.role === 'rent_invoice' && row.field === 'invoice_number').requirement, 'required')
  assert.equal(state.editor.dirty, false)
})

test('an old backend response cannot replace the newly bound backend policy', async () => {
  let resolveOld
  const oldApi = { fieldRequirements: () => new Promise(resolve => { resolveOld = resolve }) }
  const state = await harness(oldApi)
  await state.update({ api: { fieldRequirements: async () => ({ ...initial, policy_id: 'new-backend', revision: 7 }) } })
  resolveOld(initial)
  await state.update({})
  assert.equal(state.editor.policy.policy_id, 'new-backend')
  assert.equal(state.editor.policy.revision, 7)
})

function policyWithOverrides() {
  const base_requirements = initial.requirements
  const override = { role: 'rent_invoice', field: 'total', requirement: 'required', reason: 'Explicit tenant requirement.' }
  return { ...initial, base_requirements, overrides: [override], requirements: [...base_requirements, override] }
}

test('using deployment defaults stages a draft and saves an empty override policy only on Save', async () => {
  const policy = policyWithOverrides()
  let submitted
  let writes = 0
  const state = await harness({ fieldRequirements: async () => policy, saveFieldRequirements: async payload => { writes += 1; submitted = payload; return { ...policy, revision: 4, requirements: policy.base_requirements, overrides: payload.requirements } } })
  await state.act(editor => editor.onUseDeploymentDefaults())
  assert.equal(writes, 0)
  assert.equal(state.editor.dirty, true)
  assert.equal(state.editor.usingDeploymentDefaults, true)
  assert.equal(state.editor.draft.find(row => row.role === 'rent_invoice' && row.field === 'total').requirement, 'optional')
  await state.act(editor => editor.onSave({ preventDefault() {} }))
  assert.equal(JSON.stringify(submitted.requirements), '[]')
  assert.equal(state.editor.dirty, false)
  assert.equal(state.editor.usingDeploymentDefaults, false)
})

test('editing after staging deployment defaults submits only the new field delta', async () => {
  const policy = policyWithOverrides()
  let submitted
  const state = await harness({ fieldRequirements: async () => policy, saveFieldRequirements: async payload => { submitted = payload; return { ...policy, revision: 4, requirements: [...policy.base_requirements, ...payload.requirements], overrides: payload.requirements } } })
  await state.act(editor => editor.onUseDeploymentDefaults())
  await state.act(editor => editor.onChange({ role: 'tax_invoice', field: 'invoice_number' }, { requirement: 'required' }))
  await state.act(editor => editor.onSave({ preventDefault() {} }))
  assert.equal(submitted.requirements.length, 1)
  assert.equal(submitted.requirements[0].role, 'tax_invoice')
  assert.equal(submitted.requirements[0].field, 'invoice_number')
})

test('discarding staged deployment defaults retains the saved explicit overrides', async () => {
  const policy = policyWithOverrides()
  const state = await harness({ fieldRequirements: async () => policy })
  await state.act(editor => editor.onUseDeploymentDefaults())
  await state.act(editor => editor.onDiscard())
  assert.equal(state.editor.dirty, false)
  assert.equal(state.editor.usingDeploymentDefaults, false)
  assert.equal(state.editor.draft.find(row => row.role === 'rent_invoice' && row.field === 'total').requirement, 'required')
  assert.equal(state.editor.policy.overrides.length, 1)
})

test('a read-only account cannot stage deployment defaults', async () => {
  const state = await harness({ fieldRequirements: async () => ({ ...policyWithOverrides(), can_edit: false }) })
  await state.act(editor => editor.onUseDeploymentDefaults())
  assert.equal(state.editor.dirty, false)
  assert.equal(state.editor.usingDeploymentDefaults, false)
})
