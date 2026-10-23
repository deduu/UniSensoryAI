import test from 'node:test'
import assert from 'node:assert/strict'
import { fieldCurrency, isMoneyField } from '../src/paper/monetaryFields.js'

test('only known monetary schema fields receive money formatting', () => {
  for (const path of ['/fixed_rent', '/minimum_guaranteed_payment', '/subtotal', '/tax_amount', '/taxable_amount', '/total', '/vat_amount', '/withholding_amount', '/rounding_adjustment', '/installment_schedule/total_gross', '/installment_schedule/installments/0/gross_amount']) assert.equal(isMoneyField(path), true, path)
  for (const path of ['/bank_account', '/contract_number', '/withholding_policy/rate', '/revenue_share_rate', '/usage_quantity', '/extensions/total', '/extensions/fixed_rent', '/party_roles/total', '/other_key_terms/0', '', undefined]) assert.equal(isMoneyField(path), false, String(path))
})

test('field currency follows the nearest owning object without substituting an unknown schedule currency', () => {
  const data = { currency: 'IDR', fixed_rent: '1', installment_schedule: { currency: 'USD', installments: [{ gross_amount: '2' }] } }
  assert.equal(fieldCurrency(data, '/fixed_rent'), 'IDR')
  assert.equal(fieldCurrency(data, '/installment_schedule/installments/0/gross_amount'), 'USD')
  assert.equal(fieldCurrency({ ...data, installment_schedule: { currency: null, installments: [{ gross_amount: '2' }] } }, '/installment_schedule/installments/0/gross_amount'), null)
  assert.equal(fieldCurrency({}, '/total'), undefined)
})
