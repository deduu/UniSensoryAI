import { useEffect, useState, useCallback } from 'react'
import PlaygroundPanel from '../components/playground/PlaygroundPanel'
import PlaygroundResult from '../components/playground/PlaygroundResult'
import Card from '../components/ui/Card'
import { uploadDocument } from '../api/jobs'
import { useApp } from '../context/AppContext'
import { useJobs } from '../context/JobContext'
import { useJobPolling } from '../hooks/useJobPolling'

export default function Playground() {
  const { backendUrl } = useApp()
  const { addJob, getJob } = useJobs()
  const [loading, setLoading] = useState(false)
  const [activeJobId, setActiveJobId] = useState(null)
  const [error, setError] = useState(null)

  // Poll active job
  const activeJob = getJob(activeJobId)
  const isTerminal = ['completed', 'failed'].includes(activeJob?.status)
  useJobPolling(isTerminal ? null : activeJobId)

  useEffect(() => {
    document.title = 'Playground â€” Intelidoc'
  }, [])

  const handleRun = useCallback(
    async (file, modelId) => {
      setLoading(true)
      setError(null)
      try {
        const result = await uploadDocument(file, modelId, backendUrl)
        setActiveJobId(result.job_id)
        addJob({
          job_id: result.job_id,
          status: result.status,
          filename: file.name,
          fileSize: file.size,
          model_id: modelId,
          created_at: new Date().toISOString(),
          documents: [],
        })
      } catch (err) {
        setError(err.message || 'Processing failed')
      } finally {
        setLoading(false)
      }
    },
    [backendUrl, addJob]
  )

  return (
    <div>
      <h1 className="text-2xl font-bold text-ink">Playground</h1>
      <p className="mt-1 text-sm text-ink-muted">
        Test document processing with different models interactively
      </p>

      {error && (
        <p className="mt-4 rounded bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>
      )}

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-5">
        <Card className="p-5 lg:col-span-2">
          <h2 className="mb-4 text-sm font-semibold uppercase text-ink-muted">Configuration</h2>
          <PlaygroundPanel onRun={handleRun} loading={loading} />
        </Card>

        <Card className="p-5 lg:col-span-3">
          <h2 className="mb-4 text-sm font-semibold uppercase text-ink-muted">Result</h2>
          <PlaygroundResult job={activeJob} />
        </Card>
      </div>
    </div>
  )
}
