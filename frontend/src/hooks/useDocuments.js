import { useMemo, useState } from 'react'
import { useJobs } from '../context/JobContext'
import { documentForJob } from '../jobs/presentation'

/**
 * Aggregate all documents from completed jobs.
 * Supports client-side search and type filtering.
 */
export function useDocuments() {
  const { jobs } = useJobs()
  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState('all')

  const allDocuments = useMemo(() => {
    const docs = []
    for (const job of jobs) {
      if (!job.documents) continue
      for (const doc of job.documents) {
        docs.push(documentForJob(job, doc))
      }
    }
    return docs
  }, [jobs])

  const filtered = useMemo(() => {
    let result = allDocuments

    if (search.trim()) {
      const q = search.toLowerCase()
      result = result.filter(
        (d) =>
          d.filename?.toLowerCase().includes(q) ||
          d.content_text?.toLowerCase().includes(q)
      )
    }

    if (typeFilter !== 'all') {
      result = result.filter((d) => {
        const ext = d.filename?.split('.').pop()?.toLowerCase() || ''
        if (typeFilter === 'pdf') return ext === 'pdf'
        if (typeFilter === 'image') return ['png', 'jpg', 'jpeg', 'webp', 'gif'].includes(ext)
        if (typeFilter === 'office')
          return ['xlsx', 'xls', 'docx', 'doc', 'pptx', 'ppt'].includes(ext)
        return true
      })
    }

    return result
  }, [allDocuments, search, typeFilter])

  return { documents: filtered, allDocuments, search, setSearch, typeFilter, setTypeFilter }
}
