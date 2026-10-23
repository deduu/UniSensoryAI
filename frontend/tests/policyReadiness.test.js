import test from 'node:test'
import assert from 'node:assert/strict'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'
import vm from 'node:vm'
import React from 'react'
import { build } from 'esbuild'

const context = { policy_id: 'paper.match', policy_version: 'fields.1', required_invoice_fields: [], required_tax_fields: [], field_requirements: [] }
const invoice = {
  draft_id: 'invoice-draft', version_number: 2, role: 'rent_invoice', status: 'reviewed', created_by: 'reviewer',
  document: { source_document_id: 'invoice-source', fields: { invoice_number: 'INV-1', total: '9007199254740993.001' }, evidence: [], warnings: [] },
}
const source = { job_id: 'invoice-extraction', filename: 'invoice.pdf' }
const identity = { vendor_id: 'vendor-1', store_id: 'store-1', contract_number: 'contract-1' }
const association = { agreement_id: 'agreement-1', version_number: 3, reason: 'Reviewed the contract reference.' }
let compiled

async function compile() {
  if (!compiled) {
    const component = new URL('../src/components/paper/SavedDocumentWorkspace.jsx', import.meta.url)
    const built = await build({
      entryPoints: [fileURLToPath(component)], bundle: true, write: false, platform: 'node', format: 'cjs', jsx: 'automatic', packages: 'external',
      external: ['./SchemaFields', './SourceReview', './ContractAssociationReview', './CasePreparation'],
    })
    compiled = { code: built.outputFiles[0].text, require: createRequire(component) }
  }
  return compiled
}

function child(tree, name) {
  if (!tree || typeof tree !== 'object') return null
  if (Array.isArray(tree)) return tree.map(item => child(item, name)).find(Boolean) || null
  if (tree.type?.name === name) return tree
  return child(tree.props?.children, name)
}

function button(tree, label) {
  if (!tree || typeof tree !== 'object') return null
  if (Array.isArray(tree)) return tree.map(item => button(item, label)).find(Boolean) || null
  if (tree.type === 'button' && React.Children.toArray(tree.props.children).includes(label)) return tree
  return button(tree.props?.children, label)
}

async function harness(api, extra = {}) {
  const built = await compile()
  const slots = []
  let cursor = 0, effects = [], tree
  let props = { api, schemas: [], context, openRequest: { request_id: 1, record: invoice, prepare: true }, ...extra }
  const changed = (prior, dependencies) => !prior || dependencies.some((value, position) => !Object.is(value, prior.dependencies[position]))
  const hooks = {
    ...React,
    useRef(value) { const index = cursor++; slots[index] ??= { current: value }; return slots[index] },
    useState(value) { const index = cursor++; if (!(index in slots)) slots[index] = typeof value === 'function' ? value() : value; return [slots[index], next => { slots[index] = typeof next === 'function' ? next(slots[index]) : next }] },
    useCallback(callback, dependencies) { const index = cursor++; if (changed(slots[index], dependencies)) slots[index] = { dependencies, callback }; return slots[index].callback },
    useEffect(effect, dependencies) {
      const index = cursor++, prior = slots[index]
      if (changed(prior, dependencies)) {
        prior?.cleanup?.()
        effects.push(() => { slots[index] = { dependencies, cleanup: effect() } })
      }
    },
  }
  // Exercise the workspace lifecycle and child callbacks; descendant hooks are independent.
  const children = {
    './SchemaFields': Object.assign(function SchemaFields() {}, { revealInvalidField() {} }),
    './SourceReview': function SourceReview() {},
    './ContractAssociationReview': function ContractAssociationReview() {},
    './CasePreparation': function CasePreparation() {},
  }
  const module = { exports: {} }
  vm.runInNewContext(built.code, { module, exports: module.exports, require: name => name === 'react' ? hooks : children[name] || built.require(name) })
  const render = () => { cursor = 0; effects = []; tree = module.exports.default(props); effects.forEach(effect => effect()) }
  const settle = async () => { for (let index = 0; index < 8; index += 1) { await Promise.resolve(); render() } }
  render(); await settle()
  return {
    get preparation() { return child(tree, 'CasePreparation')?.props },
    get contract() { return child(tree, 'ContractAssociationReview')?.props },
    get original() { return child(tree, 'SourceReview')?.props.record },
    async act(callback) { await callback(); await settle() },
    async update(next) { props = { ...props, ...next }; render(); await settle() },
    async backToReview() { button(tree, 'Back to saved document').props.onClick(); await settle() },
  }
}

function fixture(caseReadiness) {
  const counts = { documents: 0, originals: 0, checks: 0, refreshes: 0 }
  let submitted
  const api = {
    documentDraftVersion: async () => { counts.documents += 1; return invoice },
    documentDraftVersions: async () => ({ items: [invoice] }),
    extractionByDocument: async () => { counts.originals += 1; return source },
    caseReadiness: payload => { counts.checks += 1; submitted = payload; return caseReadiness() },
  }
  return { api, counts, get submitted() { return submitted }, onRefreshPolicy: () => { counts.refreshes += 1 } }
}

async function confirmContract(state) {
  await state.act(() => state.contract.onChange({ ...state.contract.pkg, identity, association }))
  assert.equal(state.preparation.package.association.agreement_id, association.agreement_id)
}

test('a policy change discards an in-flight readiness result and preserves the selected source', async () => {
  let resolve
  const pending = new Promise(done => { resolve = done })
  const fixtureData = fixture(() => pending)
  const state = await harness(fixtureData.api, { onRefreshPolicy: fixtureData.onRefreshPolicy })
  await confirmContract(state)
  const before = state.preparation
  let checking
  await state.act(() => { checking = state.preparation.onCheck() })
  assert.equal(state.preparation.disabled, true)
  assert.equal(fixtureData.submitted.invoice.draft_id, invoice.draft_id)
  await state.update({ context: { ...context, policy_version: 'fields.2' } })
  resolve({ ready: true, ...context, checks: [] })
  await state.act(() => checking)
  assert.equal(state.preparation.readiness, null)
  assert.equal(state.preparation.disabled, false)
  assert.equal(state.preparation.selection, before.selection)
  assert.equal(state.preparation.package, before.package)
  assert.equal(state.preparation.package.invoice.fields.total, invoice.document.fields.total)
  assert.deepEqual(fixtureData.counts, { documents: 1, originals: 1, checks: 1, refreshes: 0 })
  await state.backToReview()
  assert.equal(state.original, source)
})

test('current readiness is retained until a new policy clears it without reopening the document', async () => {
  const ready = { ready: true, ...context, checks: [] }
  const fixtureData = fixture(async () => ready)
  const state = await harness(fixtureData.api)
  await confirmContract(state)
  await state.act(() => state.preparation.onCheck())
  assert.equal(state.preparation.readiness, ready)
  assert.equal(state.preparation.disabled, false)
  const before = state.preparation
  await state.update({ context: { ...context, policy_version: 'fields.2' } })
  assert.equal(state.preparation.readiness, null)
  assert.equal(state.preparation.disabled, false)
  assert.equal(state.preparation.selection, before.selection)
  assert.equal(state.preparation.package, before.package)
  assert.deepEqual(fixtureData.counts, { documents: 1, originals: 1, checks: 1, refreshes: 0 })
  await state.backToReview()
  assert.equal(state.original, source)
})
