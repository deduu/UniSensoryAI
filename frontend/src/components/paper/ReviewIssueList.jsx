import CanonicalValue from './CanonicalValue.js'
import { fieldCurrency } from '../../paper/monetaryFields.js'
import './reviewIssueList.css'

const citationLabel = status => status === 'verified' ? 'Quote traceability verified; meaning still requires review.' : status === 'unavailable' ? 'Original source unavailable for verification.' : 'Citation requires review.'

/** Show field, reason and next action while retaining every assessed diagnostic in Details. */
export default function ReviewIssueList({ groups = [], record, onNavigate, onInspect, data = {} }) {
  return <div className="paper-issue-list">{groups.map(group => <article key={group.key} className={`paper-issue-row paper-issue-row--${group.status}`}>
    <header className="paper-issue-row-header">
      <h4>{group.label}</h4>
      <span>{group.status === 'history' ? 'Extraction history' : group.valueState === 'present' ? 'Value needs confirmation' : group.valueState === 'empty' ? 'No entries recorded' : 'Value not established'}</span>
    </header>
    <div className="paper-issue-actions-list">{group.summaries.map((summary, index) => <div key={index} className="paper-issue-summary">
      <p>{summary.why}</p>
      <p className="paper-issue-next"><span>Next:</span> {summary.nextAction}</p>
    </div>)}</div>
    <div className="paper-issue-shortcuts">
      {group.fieldPath && onInspect && <button type="button" className="paper-source-link" onClick={() => onInspect(group.fieldPath, group.label)}>Review field</button>}
      {record && group.pages.map(page => <button key={page} type="button" className="paper-source-link" aria-label={`Open ${group.label.toLowerCase()} source page ${page}`} disabled={!onNavigate} onClick={() => onNavigate?.(page)}>p. {page}</button>)}
    </div>
    <details className="paper-issue-details">
      <summary>Details · {group.issueCount} retained {group.issueCount === 1 ? 'entry' : 'entries'}</summary>
      {group.fieldPath && <p className="paper-issue-path">Field: {group.fieldPath}</p>}
      {group.fieldPath && <section className="paper-issue-current" aria-label={`Current value of ${group.label.toLowerCase()}`}><h5>Current value</h5><CanonicalValue value={group.value} fieldPath={group.fieldPath} currency={fieldCurrency(data, group.fieldPath)} formatted={typeof group.value === 'string' && group.value.length > 160} /></section>}
      {group.items.map((item, index) => <section key={index} className="paper-issue-retained">
        <h5>Entry {index + 1} · {item.status === 'history' ? 'Extraction history' : 'Needs review'}</h5>
        <p>{typeof item.issue === 'string' ? item.issue : item.issue?.message || 'No diagnostic message supplied.'}</p>
        {item.reason && <p>{item.reason}</p>}
        <p>{citationLabel(item.citationStatus)}</p>
        <details><summary>Exact retained entry (JSON)</summary><pre>{JSON.stringify(item.issue, null, 2)}</pre></details>
      </section>)}
    </details>
  </article>)}</div>
}
