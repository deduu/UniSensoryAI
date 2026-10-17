import { createContext, useContext } from 'react'
import { FileSearch, MessageSquareQuote } from 'lucide-react'
import { fieldEvidencePages } from '../../paper/sourceReview'

export const FieldSourceContext = createContext(null)

/** Source shortcuts work with arbitrary schema pointers and retain every uniquely linked page. */
export default function FieldSourceLinks({ fieldPath, label }) {
  const context = useContext(FieldSourceContext)
  if (!context?.record) return null
  const { pages, unresolved, citationCount } = fieldEvidencePages(context.record, fieldPath, context.evidence)
  const name = label || fieldPath
  const details = event => ({ fieldPath, label: name, evidence: context.evidence, returnTarget: event.currentTarget })
  const description = unresolved.length ? 'Some citations could not be linked. Review field evidence for details.' : 'Source citations locate extracted text; verify the value and its meaning.'
  if (!pages.length) return <button type="button" className="inline-flex items-center gap-1 text-[11px] font-normal text-ink-faint" aria-label={`View evidence for ${name}: no linked source`} title={citationCount ? 'Citations have no unique page link. Open field evidence for details.' : 'No source citation was returned for this field. Open field evidence for details.'} onClick={event => context.onInspect?.(details(event))}><FileSearch size={13} aria-hidden="true" /><span>No linked source</span></button>
  const pageButton = page => <button key={page} type="button" className="paper-source-link" aria-label={`Show source for ${name} on page ${page}`} title={description} onClick={event => context.onJump(page, name, details(event))}><FileSearch size={13} aria-hidden="true" /><span>p. {page}</span></button>
  const evidenceButton = context.onInspect && <button type="button" className="paper-source-link" aria-label={`View evidence for ${name}`} title="Read this field’s quotes without leaving your place" onClick={event => context.onInspect(details(event))}><MessageSquareQuote size={13} aria-hidden="true" /><span>Evidence</span></button>
  if (pages.length === 1) return <span className="inline-flex min-w-0 flex-wrap items-start gap-1">{pageButton(pages[0])}{evidenceButton}</span>
  return <div className="flex min-w-0 flex-wrap items-start gap-1"><details className="paper-field-sources min-w-0 text-xs font-normal">
    <summary aria-label={`Source pages for ${name}`} className="paper-source-link cursor-pointer" title={description}><FileSearch size={13} aria-hidden="true" /><span>{pages.length} pages</span></summary>
    <div className="mt-2 flex flex-wrap gap-1.5" role="group" aria-label={`Source pages for ${name}`}>{pages.map(pageButton)}</div>
    {unresolved.length > 0 && <p className="mt-1 text-[11px] text-ink-muted">Some citations have no unique page link.</p>}
  </details>{evidenceButton}</div>
}
