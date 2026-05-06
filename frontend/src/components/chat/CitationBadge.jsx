import { useState } from 'react'
import { FileText } from 'lucide-react'

export default function CitationBadge({ index, citation }) {
  const [showTooltip, setShowTooltip] = useState(false)

  return (
    <span className="relative inline-block">
      <button
        className="inline-flex items-center justify-center h-5 min-w-[20px] px-1 rounded text-[10px] font-bold 
                   bg-brand/20 text-brand-hover border border-brand/30
                   hover:bg-brand/30 hover:border-brand/50 hover:shadow-[0_0_8px_rgba(99,102,241,0.3)]
                   transition-all duration-200 cursor-pointer align-super"
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
      >
        {index}
      </button>
      {showTooltip && citation && (
        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-50 w-72 animate-fade-in">
          <div className="rounded-xl border border-surface-border bg-surface-muted/95 backdrop-blur-md p-3 shadow-modal">
            <div className="flex items-center gap-2 mb-1.5">
              <FileText className="h-3.5 w-3.5 text-brand shrink-0" />
              <span className="text-xs font-medium text-ink truncate">
                {citation.filename || 'Document'}
              </span>
            </div>
            {citation.excerpt && (
              <p className="text-[11px] text-ink-muted leading-relaxed line-clamp-3">
                "{citation.excerpt}"
              </p>
            )}
          </div>
          <div className="absolute left-1/2 -translate-x-1/2 -bottom-1 w-2 h-2 rotate-45 bg-surface-muted/95 border-r border-b border-surface-border" />
        </div>
      )}
    </span>
  )
}
