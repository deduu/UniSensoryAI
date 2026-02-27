import { useEffect, useState } from 'react'
import DocumentSearch from '../components/documents/DocumentSearch'
import DocumentGrid from '../components/documents/DocumentGrid'
import ContentViewer from '../components/documents/ContentViewer'
import { useDocuments } from '../hooks/useDocuments'

const TYPE_TABS = [
  { key: 'all', label: 'All' },
  { key: 'pdf', label: 'PDF' },
  { key: 'image', label: 'Images' },
  { key: 'office', label: 'Office' },
]

export default function Documents() {
  const { documents, search, setSearch, typeFilter, setTypeFilter } = useDocuments()
  const [viewDoc, setViewDoc] = useState(null)

  useEffect(() => {
    document.title = 'Documents — UniSensoryAI'
  }, [])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-ink">Documents</h1>
        <p className="mt-1 text-sm text-ink-muted">
          Browse all extracted documents from processed jobs
        </p>
      </div>

      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <DocumentSearch value={search} onChange={setSearch} />
        <div className="flex gap-1">
          {TYPE_TABS.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setTypeFilter(tab.key)}
              className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                typeFilter === tab.key
                  ? 'bg-brand text-white'
                  : 'text-ink-muted hover:bg-surface-subtle'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      <DocumentGrid documents={documents} onViewFull={setViewDoc} />

      <ContentViewer
        doc={viewDoc}
        open={!!viewDoc}
        onClose={() => setViewDoc(null)}
      />
    </div>
  )
}
