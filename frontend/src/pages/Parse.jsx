import { useEffect, useState } from 'react'
import Tabs from '../components/ui/Tabs'
import DropZone from '../components/upload/DropZone'
import FilePreview from '../components/upload/FilePreview'
import UploadProgress from '../components/upload/UploadProgress'
import Button from '../components/ui/Button'
import JobTable from '../components/jobs/JobTable'
import JobDetailPanel from '../components/jobs/JobDetailPanel'
import { useFileUpload } from '../hooks/useFileUpload'
import { useJobList } from '../hooks/useJobList'
import { useJobPolling } from '../hooks/useJobPolling'
import { useApp } from '../context/AppContext'
import { useJobs } from '../context/JobContext'
import { deleteJob } from '../api/jobs'
import { AVAILABLE_MODELS } from '../api/models'

function UploadTab() {
  const { files, state, error, lastJobId, addFiles, removeFile, upload, reset, STATES } =
    useFileUpload()
  const [modelId, setModelId] = useState(AVAILABLE_MODELS[0].id)

  // Poll the latest submitted job
  useJobPolling(
    state === STATES.SUBMITTED || state === STATES.DONE ? lastJobId : null
  )

  // Auto-reset after upload completes so user can immediately upload again
  useEffect(() => {
    if (state === STATES.DONE) {
      const timer = setTimeout(reset, 3000)
      return () => clearTimeout(timer)
    }
  }, [state, reset, STATES])

  return (
    <div className="space-y-5">
      <DropZone onFiles={addFiles} />

      {files.length > 0 && (
        <div className="space-y-2">
          {files.map((f, i) => (
            <FilePreview
              key={`${f.name}-${i}`}
              file={f}
              index={i}
              onRemove={state === STATES.FILES_SELECTED ? removeFile : undefined}
            />
          ))}
        </div>
      )}

      <div>
        <label className="mb-1.5 block text-sm font-medium text-ink">Model</label>
        <select
          value={modelId}
          onChange={(e) => setModelId(e.target.value)}
          className="w-full rounded-lg border border-surface-border bg-surface-muted px-3 py-2.5 text-sm text-ink focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/20"
        >
          {AVAILABLE_MODELS.map((m) => (
            <option key={m.id} value={m.id}>
              {m.name} ({m.providerLabel})
            </option>
          ))}
        </select>
      </div>

      <UploadProgress state={state} error={error} STATES={STATES} />

      <div className="flex gap-3">
        <Button
          onClick={() => upload(modelId)}
          disabled={files.length === 0 || state === STATES.UPLOADING}
          loading={state === STATES.UPLOADING}
        >
          Process Documents
        </Button>
        {(state === STATES.DONE || state === STATES.ERROR) && (
          <Button variant="secondary" onClick={reset}>
            Upload More
          </Button>
        )}
      </div>
    </div>
  )
}

function JobsTab() {
  const { backendUrl } = useApp()
  const { removeJob } = useJobs()
  const { jobs } = useJobList()
  const [selectedJob, setSelectedJob] = useState(null)
  const [deleteError, setDeleteError] = useState(null)

  async function handleDeleteJob(job) {
    setDeleteError(null)
    try {
      await deleteJob(job.job_id, backendUrl)
      removeJob(job.job_id)
      if (selectedJob?.job_id === job.job_id) {
        setSelectedJob(null)
      }
    } catch (err) {
      setDeleteError(err.message || 'Failed to delete job')
    }
  }

  return (
    <div className="relative">
      {deleteError && (
        <p className="mb-3 rounded bg-red-50 px-3 py-2 text-sm text-red-700">{deleteError}</p>
      )}
      <JobTable
        jobs={jobs}
        onSelectJob={setSelectedJob}
        onDeleteJob={handleDeleteJob}
      />
      {selectedJob && (
        <JobDetailPanel job={selectedJob} onClose={() => setSelectedJob(null)} />
      )}
    </div>
  )
}

export default function Parse() {
  useEffect(() => {
    document.title = 'Parse â€” Intelidoc'
  }, [])

  return (
    <div>
      <h1 className="text-2xl font-bold text-ink">Parse Documents</h1>
      <p className="mt-1 text-sm text-ink-muted">
        Upload documents for AI-powered extraction and analysis
      </p>

      <Tabs
        className="mt-6"
        tabs={[
          { key: 'upload', label: 'Upload', content: <UploadTab /> },
          { key: 'jobs', label: 'Jobs', content: <JobsTab /> },
        ]}
      />
    </div>
  )
}
