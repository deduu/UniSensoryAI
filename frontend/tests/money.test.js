import test from 'node:test'
import assert from 'node:assert/strict'
import {
  formatMoney, formatMoneyAmount, moneyInputValidity, parseMoneyInput,
} from '../src/paper/money.js'

test('IDR grouping and decimal commas preserve exact scale and signs', () => {
  assert.equal(formatMoney('327777777.00', 'IDR'), 'IDR 327.777.777,00')
  assert.equal(formatMoneyAmount('-1234567.000100', 'IDR'), '-1.234.567,000100')
  assert.equal(formatMoneyAmount('0', 'IDR'), '0')
  assert.equal(formatMoneyAmount('-0.000', 'IDR'), '-0,000')
  assert.equal(formatMoneyAmount('0.00000001', 'IDR'), '0,00000001')
})

test('explicit other currencies use English separators without changing decimals', () => {
  assert.equal(formatMoney('1234567.12000', 'USD'), 'USD 1,234,567.12000')
  assert.equal(formatMoney('-1234.00', 'EUR', { withCurrency: false }), '-1,234.00')
  assert.equal(formatMoney('1234.00', ' usd '), 'USD 1,234.00')
})

test('amounts larger than safe integers and very small fractions remain exact', () => {
  const amount = '900719925474099312345678901234567890.0000000000000000000100'
  assert.equal(formatMoneyAmount(amount, 'IDR'), '900.719.925.474.099.312.345.678.901.234.567.890,0000000000000000000100')
  assert.equal(parseMoneyInput(formatMoneyAmount(amount, 'IDR'), 'IDR'), amount)
  assert.equal(parseMoneyInput(formatMoneyAmount(amount, 'USD'), 'USD'), amount)
})

test('missing currency uses Indonesian separators without inventing a code', () => {
  for (const currency of [null, undefined, '', 'unknown']) {
    assert.equal(formatMoney('1234.50', currency), '1.234,50')
    assert.equal(parseMoneyInput('1.234,50', currency), '1234.50')
  }
})

test('formatting keeps malformed and non-string source values visibly unchanged', () => {
  for (const value of ['1e6', '+123', '1,234.00', '12.345,00', ' 12.00 ', '01.00', '12.', 'NaN', 'unknown', '--5']) {
    assert.equal(formatMoney(value, 'IDR'), value)
    assert.equal(formatMoneyAmount(value, 'USD'), value)
  }
  assert.equal(formatMoney(1234567, 'IDR'), '1234567')
  assert.equal(formatMoney(false, 'USD'), 'false')
  assert.equal(formatMoney(null, 'IDR'), '')
  assert.equal(formatMoney(undefined, 'IDR'), '')
  assert.equal(formatMoney('', 'IDR'), '')
})

test('local input accepts either ungrouped or strictly grouped amounts', () => {
  for (const [input, canonical] of [['1234567,00', '1234567.00'], ['1.234.567,00', '1234567.00'], ['-1.234,0500', '-1234.0500'], ['0,00', '0.00'], ['-0', '-0'], [' 1.234,50 ', '1234.50']]) {
    assert.equal(parseMoneyInput(input, 'IDR'), canonical)
  }
  assert.equal(parseMoneyInput('1,234,567.00', 'USD'), '1234567.00')
  assert.equal(parseMoneyInput('-1234.000', 'USD'), '-1234.000')
})

test('input interpretation follows the selected locale without guessing separators', () => {
  assert.equal(parseMoneyInput('1.234', 'IDR'), '1234')
  assert.equal(parseMoneyInput('1.234', 'USD'), '1.234')
  assert.equal(parseMoneyInput('1,234', 'USD'), '1234')
  assert.equal(parseMoneyInput('1,234', 'IDR'), '1.234')
  for (const input of ['1234.50', '1,234.50', '1.23.456', '1234.567,00', '1.2345', '1.234,', ',', '-0,', '01', '1e3', 'IDR 1.000', '- 12', '1 000', '+12']) {
    assert.throws(() => parseMoneyInput(input, 'IDR'), /amount|decimal|separator|group/i, input)
  }
  for (const input of ['1234,50', '1.234,50', '1,23,456', '1234,567.00', '1,2345', '1,234.', '.5', '0.', '1e3']) {
    assert.throws(() => parseMoneyInput(input, 'USD'), /amount|decimal|separator|group/i, input)
  }
})

test('empty input remains empty and never becomes zero or unknown', () => {
  assert.equal(parseMoneyInput('', 'IDR'), '')
  assert.equal(parseMoneyInput('   ', 'USD'), '')
  for (const input of [null, undefined, 0, 1n, {}, []]) assert.throws(() => parseMoneyInput(input, 'IDR'), /amount|text/i)
})

test('invalid and unapplied local text prevents submission without changing saved values', () => {
  const current = '1234.50'
  assert.equal(moneyInputValidity('1.234,50', current, 'IDR'), '')
  assert.match(moneyInputValidity('1.234,', current, 'IDR'), /amount|decimal|separator|group/i)
  assert.match(moneyInputValidity('2.000,00', current, 'IDR'), /apply|saved|update/i)
  assert.match(moneyInputValidity('', current, 'IDR'), /apply|saved|update/i)
  assert.equal(moneyInputValidity('', '', 'IDR'), '')
  assert.equal(current, '1234.50')
})
