import test, { after, before } from 'node:test'
import assert from 'node:assert/strict'
import { fileURLToPath } from 'node:url'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'
import react from '@vitejs/plugin-react'

let server
let SchemaFields
let CanonicalValue
let AgreementPaymentRules
let InvoicePaymentReview
before(async () => {
  server = await createServer({ root: fileURLToPath(new URL('..', import.meta.url)), configFile: false, plugins: [react()], server: { middlewareMode: true, hmr: false, watch: null } })
  SchemaFields = (await server.ssrLoadModule('/src/components/paper/SchemaFields.jsx')).default
  CanonicalValue = (await server.ssrLoadModule('/src/components/paper/CanonicalValue.js')).default
  AgreementPaymentRules = (await server.ssrLoadModule('/src/components/paper/AgreementPaymentRules.jsx')).default
  InvoicePaymentReview = (await server.ssrLoadModule('/src/components/paper/InvoicePaymentReview.jsx')).default
})
after(async () => { await server?.close() })

const schema = { type: 'object', properties: {
  vendor_name: { type: ['string', 'null'], title: 'Landlord' },
  'other/terms': { type: ['array', 'null'], title: 'Other terms', items: { type: 'string' } },
  payment_schedule: { type: ['string', 'null'], title: 'Payment schedule', maxLength: 24000 },
  extensions: { type: 'object', title: 'Settings' },
} }
const values = { vendor_name: 'Example Owner', 'other/terms': ['  **First clause**\nfull text  ', 'Second clause'], payment_schedule: '**Payable:** full paragraph', extensions: { basis: 'annual', enabled: false } }
const render = props => renderToStaticMarkup(createElement(SchemaFields, { schema, value: values, onChange: () => {}, ...props }))

test('read-only review presents complete readable cards without disabled form controls', () => {
  const html = render({ disabled: true })
  assert.doesNotMatch(html, /<(?:input|select|textarea)\b/)
  assert.match(html, /paper-readonly-field/)
  assert.match(html, /Example Owner/)
  assert.match(html, /<strong>First clause<\/strong>/)
  assert.match(html, /<strong>Payable:<\/strong>/)
  assert.match(html, /data-review-field="\/other~1terms\/1"/)
  assert.match(html, /Basis/)
  assert.match(html, /false/)
})

test('clause editing exposes ordinary labelled textareas with an advanced JSON alternative', () => {
  const html = render({ only: ['other/terms'] })
  assert.match(html, /Clause 1/)
  assert.match(html, /Clause 2/)
  assert.match(html, /Add clause/)
  assert.match(html, /Advanced JSON editor/)
  assert.match(html, /Apply other terms/)
  assert.match(html, /data-review-field="\/other~1terms\/0"/)
  assert.match(html, /rows="5"/)
  assert.ok(html.includes('  **First clause**\nfull text  '))
})

test('unknown and empty lists stay distinct and nonstring lists retain JSON editing', () => {
  assert.match(render({ only: ['other/terms'], value: { 'other/terms': null } }), /Set empty list/)
  assert.match(render({ only: ['other/terms'], value: { 'other/terms': [] } }), /No clauses/)
  const html = render({ only: ['other/terms'], value: { 'other/terms': ['text', null] } })
  assert.doesNotMatch(html, /Add clause/)
  assert.match(html, /Apply JSON to update/)
})

test('money uses exact grouping while account numbers, rates and quantities remain literal', () => {
  const moneySchema = { type: 'object', properties: Object.fromEntries(['currency', 'fixed_rent', 'bank_account', 'revenue_share_rate', 'usage_quantity'].map(key => [key, { type: ['string', 'null'] }])) }
  const value = { currency: 'IDR', fixed_rent: '9007199254740993.00', bank_account: '001234567890', revenue_share_rate: '0.10', usage_quantity: '1234.50' }
  const before = structuredClone(value)
  const html = render({ schema: moneySchema, value, disabled: true })
  assert.match(html, /IDR 9\.007\.199\.254\.740\.993,00/)
  assert.match(html, /001234567890/)
  assert.match(html, /0\.10/)
  assert.match(html, /1234\.50/)
  assert.deepEqual(value, before)
  const edit = render({ schema: moneySchema, value, only: ['fixed_rent'] })
  assert.match(edit, /value="9\.007\.199\.254\.740\.993,00"/)
})

test('nested schedule amounts use their own currency while raw JSON remains exact', () => {
  const value = { currency: 'USD', total_gross: '9007199254740993.00', installments: [{ gross_amount: '-1234.500', installment_id: '001234', conditions: [] }], extensions: { total: '1234.50' } }
  const html = renderToStaticMarkup(createElement(CanonicalValue, { value, fieldPath: '/installment_schedule', currency: 'IDR' }))
  assert.match(html, /USD 9,007,199,254,740,993\.00/)
  assert.match(html, /USD -1,234\.500/)
  assert.match(html, /001234/)
  assert.match(html, /9007199254740993\.00/)
  assert.match(html, /1234\.50/)
  assert.equal(value.installments[0].gross_amount, '-1234.500')
})

test('payment editors and invoice arithmetic render grouped amounts without modifying their inputs', () => {
  const terms = { currency: 'IDR', installment_schedule: { currency: 'IDR', total_gross: '1638888888', installments: [{ installment_id: 'first', gross_amount: '983333333', conditions: [] }] } }
  const agreementHtml = renderToStaticMarkup(createElement(AgreementPaymentRules, { schema: {}, terms }))
  assert.match(agreementHtml, /IDR 1\.638\.888\.888 gross/)
  assert.match(agreementHtml, /value="1\.638\.888\.888"/)
  assert.match(agreementHtml, /value="983\.333\.333"/)
  const fields = { currency: 'IDR', subtotal: '1000.00', vat_amount: '0', withholding_amount: '100.00', rounding_adjustment: '-0.50', total: '899.50' }
  const pkg = { invoice: { fields } }
  const before = structuredClone(pkg)
  const invoiceHtml = renderToStaticMarkup(createElement(InvoicePaymentReview, { pkg, disabled: true }))
  assert.match(invoiceHtml, /IDR 1\.000,00/)
  assert.match(invoiceHtml, /IDR 899,50/)
  // The existing arithmetic helper normalizes its derived result; source scale stays intact.
  assert.match(invoiceHtml, /<strong>899,5<\/strong>/)
  assert.match(invoiceHtml, /value="-0,50"/)
  assert.deepEqual(pkg, before)
})
