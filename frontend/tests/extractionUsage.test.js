import test from 'node:test'
import assert from 'node:assert/strict'
import { usagePresentation } from '../src/paper/extractionUsage.js'

test('historical and unreported usage stays unavailable rather than zero', () => {
  for (const value of [undefined, null, { coverage: 'unavailable', cost_coverage: 'unavailable', total_tokens: null, estimated_cost: null }]) {
    const view = usagePresentation(value)
    assert.equal(view.tokens, 'Unavailable')
    assert.equal(view.cost, 'Unavailable')
    assert.equal(view.tokenLabel, 'Reported tokens')
  }
})

test('complete measured usage preserves small cost precision and labels it an estimate', () => {
  const view = usagePresentation({ coverage: 'complete', cost_coverage: 'complete', total_tokens: 1234, estimated_cost: '0.00432125', currency: 'USD', measured_call_count: 2, call_count: 2 })
  assert.equal(view.tokens, '1,234')
  assert.equal(view.tokenLabel, 'Total reported tokens')
  assert.equal(view.cost, 'USD 0.004321')
  assert.equal(view.costLabel, 'Estimated cost')
  assert.equal(view.coverage, '2 of 2 calls metered')
})

test('incomplete metering and pricing are clearly known subtotals, not totals', () => {
  const view = usagePresentation({ coverage: 'partial', cost_coverage: 'partial', total_tokens: 100, estimated_cost: '0.01', currency: 'USD', measured_call_count: 1, call_count: 3 })
  assert.equal(view.tokenLabel, 'Known token subtotal')
  assert.equal(view.costLabel, 'Known cost estimate')
  assert.match(view.coverage, /1 of 3/)
  assert.equal(usagePresentation({ coverage: 'complete', cost_coverage: 'unavailable', total_tokens: 100 }).cost, 'Unavailable')
})

test('invalid counters and pricing never render NaN, negative charges, or fabricated zero', () => {
  for (const value of [NaN, -1, true, '10']) assert.equal(usagePresentation({ coverage: 'complete', total_tokens: value }).tokens, 'Unavailable')
  for (const value of ['NaN', '-1', '', null]) assert.equal(usagePresentation({ estimated_cost: value, currency: 'USD' }).cost, 'Unavailable')
  assert.equal(usagePresentation({ estimated_cost: '0.00000001', currency: 'USD' }).cost, 'USD <0.000001')
  assert.equal(usagePresentation({ estimated_cost: '1E-8', currency: 'USD' }).cost, 'USD <0.000001')
  assert.equal(usagePresentation({ estimated_cost: '0', currency: 'USD', coverage: 'complete', total_tokens: 0 }).cost, 'USD 0.00')
})
