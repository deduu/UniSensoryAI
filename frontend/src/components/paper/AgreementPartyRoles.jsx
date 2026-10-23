import FieldSourceLinks from './FieldSourceLinks'
import { changePartyRepresentative, changePartyRole, partyRoleReview } from '../../paper/agreementPartyReview'
import './agreementPartyRoles.css'

const LABELS = { landlord: 'Landlord / rent supplier', tenant: 'Tenant / customer', other: 'Other party', unknown: 'Role unresolved' }

function PartyField({ label, path, value, editable, onChange, role = false, disabled = false, nullable = true }) {
  return <div className="paper-party-field" data-review-field={path}>
    <div className="paper-party-field-heading"><span>{label}</span><FieldSourceLinks fieldPath={path} label={label} /></div>
    {editable ? <label className="block"><span className="sr-only">{label}</span>{role ? <select className="paper-input" value={value || 'unknown'} disabled={disabled} onChange={event => onChange(event.target.value)}>{Object.entries(LABELS).map(([key, text]) => <option key={key} value={key}>{text}</option>)}</select> : <input className="paper-input" value={value ?? ''} maxLength={256} disabled={disabled} required={!nullable} onChange={event => onChange(nullable && event.target.value === '' ? null : event.target.value)} />}</label> : <p>{role ? LABELS[value] || LABELS.unknown : value || 'Unknown — inspect the source'}</p>}
  </div>
}

/** Keep legal principals, source role clauses and representation chains visible together. */
export default function AgreementPartyRoles({ terms, identity, onChange, disabled = false, acknowledged = false }) {
  const review = partyRoleReview(terms)
  const editable = Boolean(onChange)
  if (!review.present) return <section className="paper-party-review paper-party-legacy" aria-label="Legal parties review"><h3>Legal parties review</h3><p>This version has no structured landlord and tenant record. Its supplier name has not been checked against explicit party roles. Review the original before creating a correction; earlier approvals remain in history.</p>{onChange && <p>Add source-supported party roles in Additional source attributes → Extensions, or rerun extraction. Do not infer the landlord from party order or a representative’s name.</p>}</section>

  const updateParty = (index, field, value) => onChange?.(changePartyRole(terms, index, field, value))
  const updateRepresentative = (index, representativeIndex, field, value) => onChange?.(changePartyRepresentative(terms, index, representativeIndex, field, value))
  return <section className="paper-party-review" aria-label="Legal parties and representation review">
    <header><h3>Legal parties and representation</h3><span className={acknowledged ? 'paper-party-reviewed' : 'paper-party-needs-review'}>{acknowledged ? 'Reviewer acknowledgement recorded' : 'Needs review'}</span></header>
    <p>Read the operative role clauses and the full representation chain across pages. A name appearing in a quote does not establish whether it is the landlord, tenant or representative.</p>
    <div className="paper-party-supplier" data-review-field="/vendor_name"><div><strong>Extracted rent supplier (vendor name)</strong><p>{review.supplier || 'Unknown'}</p><FieldSourceLinks fieldPath="/vendor_name" label="Rent supplier name" /></div>{identity && <div><strong>Assigned vendor ID</strong><p>{identity.vendor_id || 'Not assigned'}</p><span>This host ID is separate from the source name.</span></div>}</div>
    {!review.supported && <p className="paper-notice">The stored party metadata is incomplete or has an unsupported version. Correct Extensions before saving and approving. Acknowledgement cannot resolve invalid metadata.</p>}
    {review.supported && !review.parties.length && <p className="paper-notice">No legal principal was established. Add source-supported parties in Extensions before approval.</p>}
    <div className="paper-party-cards">{review.parties.map(party => <article key={party.index} className="paper-party-card" data-review-field={party.path}>
      <div className="paper-party-card-title"><h4>{LABELS[party.role]}</h4><FieldSourceLinks fieldPath={party.path} label={`${LABELS[party.role]} complete representation`} /></div>
      <PartyField label={`Principal name · party ${party.index + 1}`} path={`${party.path}/name`} value={party.name} editable={editable} disabled={disabled} onChange={value => updateParty(party.index, 'name', value)} />
      <PartyField label={`Party role · party ${party.index + 1}`} path={`${party.path}/role`} value={party.role} role editable={editable} disabled={disabled} onChange={value => updateParty(party.index, 'role', value)} />
      <PartyField label={`Exact source role · party ${party.index + 1}`} path={`${party.path}/source_role`} value={party.sourceRole} editable={editable} disabled={disabled} onChange={value => updateParty(party.index, 'source_role', value)} />
      {party.representatives.length ? <div className="paper-party-representatives"><h5>Representation chain</h5>{party.representatives.map(representative => <div key={representative.index} className="paper-party-representative" data-review-field={representative.path}><FieldSourceLinks fieldPath={representative.path} label={`Representative ${representative.index + 1} for party ${party.index + 1}`} />{[['name', 'Representative'], ['represents', 'Acts for principal'], ['capacity', 'Source capacity']].map(([field, label]) => <PartyField key={field} label={`${label} · party ${party.index + 1}, step ${representative.index + 1}`} path={`${representative.path}/${field}`} value={representative[field]} editable={editable} disabled={disabled} nullable={field !== 'name'} onChange={value => updateRepresentative(party.index, representative.index, field, value)} />)}</div>)}</div> : <p className="paper-party-empty-chain">No representative chain was extracted. Verify direct signature or complete the source-supported chain.</p>}
    </article>)}</div>
    {onChange && <p>Corrections above change the draft’s party metadata only. Correct Vendor name separately in Parties and premises; retained evidence must support every correction. Add or remove parties and representation steps under Additional source attributes → Extensions.</p>}
  </section>
}
