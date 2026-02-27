import DocumentCard from './DocumentCard'
import EmptyState from '../ui/EmptyState'
import { FileText } from 'lucide-react'

export default function DocumentGrid({ documents, onViewFull }) {
  if (documents.length === 0) {
    return (
      <EmptyState
        icon={FileText}
        heading="No documents found"
        subtext="Documents will appear here after processing completes"
      />
    )
  }

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {documents.map((doc, i) => (
        <DocumentCard key={doc.id || i} doc={doc} onViewFull={onViewFull} />
      ))}
    </div>
  )
}
