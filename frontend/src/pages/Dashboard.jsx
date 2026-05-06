import { useEffect, useState } from 'react'
import { FileUp, CheckCircle2, Clock } from 'lucide-react'
import Card from '../components/ui/Card'
import JobTable from '../components/jobs/JobTable'
import JobDetailPanel from '../components/jobs/JobDetailPanel'
import { useJobs } from '../context/JobContext'
import { useApp } from '../context/AppContext'
import DropZone from '../components/upload/DropZone'
import FilePreview from '../components/upload/FilePreview'
import UploadProgress from '../components/upload/UploadProgress'
import Button from '../components/ui/Button'
import { useFileUpload } from '../hooks/useFileUpload'
import { useJobPolling } from '../hooks/useJobPolling'
import { AVAILABLE_MODELS } from '../api/models'

function StatCard({ icon: Icon, label, value, color = 'text-brand', delay = '0ms' }) {
  return (
    <Card className="flex items-center gap-4 p-5 animate-slide-up-fade" style={{ animationDelay: delay, animationFillMode: 'both' }}>
      <div className={`relative flex h-12 w-12 items-center justify-center rounded-xl bg-surface-muted/50 border border-surface-border ${color} shadow-[inset_0_0_15px_rgba(255,255,255,0.05)]`}>
        <Icon className="h-6 w-6 relative z-10" />
        <div className={`absolute inset-0 blur-md opacity-20 bg-current rounded-xl`}></div>
      </div>
      <div>
        <p className="text-2xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-white to-white/80">{value}</p>
        <p className="text-sm text-ink-muted">{label}</p>
      </div>
    </Card>
  )
}

export default function Dashboard() {
  const { jobs } = useJobs()
  const [selectedJob, setSelectedJob] = useState(null)
  
  // Upload State
  const { files, state, error, lastJobId, addFiles, removeFile, upload, reset, STATES } = useFileUpload()
  const [modelId, setModelId] = useState(AVAILABLE_MODELS[0].id)
  const [startPage, setStartPage] = useState('')
  const [endPage, setEndPage] = useState('')

  // Page range validation
  const pageRangeError = (startPage && endPage && Number(startPage) > Number(endPage))
    ? 'Start page cannot be greater than end page.'
    : null

  useJobPolling(
    state === STATES.SUBMITTED || state === STATES.DONE ? lastJobId : null
  )

  useEffect(() => {
    document.title = 'Dashboard — UniSensoryAI'
  }, [])

  // Auto-reset upload area after done so they can upload more
  useEffect(() => {
    if (state === STATES.DONE) {
      const timer = setTimeout(() => {
        reset()
        setStartPage('')
        setEndPage('')
        // Open the completed job
        const job = jobs.find(j => j.job_id === lastJobId)
        if (job) setSelectedJob(job)
      }, 1500)
      return () => clearTimeout(timer)
    }
  }, [state, reset, STATES, jobs, lastJobId])

  const total = jobs.length
  const completed = jobs.filter((j) => j.status === 'completed').length
  const processing = jobs.filter(
    (j) => j.status === 'processing' || j.status === 'queued' || j.status === 'pending'
  ).length

  const recentJobs = jobs.slice(0, 10)

  const handleUpload = () => {
    const sp = startPage ? Number(startPage) : null
    const ep = endPage ? Number(endPage) : null
    upload(modelId, sp, ep)
  }

  return (
    <div className="space-y-8 pb-10">
      <div>
        <h1 className="text-3xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-white to-white/70 tracking-tight animate-slide-up-fade">Parse Documents</h1>
        <p className="mt-1 text-sm text-ink-muted animate-slide-up-fade" style={{ animationDelay: '100ms', animationFillMode: 'both' }}>
          Drop a document below to extract its contents using Vision-Language AI.
        </p>
      </div>

      {/* Massive LlamaParse style Drag and Drop Area */}
      <Card className="p-8 animate-slide-up-fade" style={{ animationDelay: '200ms', animationFillMode: 'both' }}>
        <div className="max-w-2xl mx-auto space-y-6">
          <DropZone onFiles={addFiles} className="py-12" />
          
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

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 items-end">
            <div className="w-full">
              <label className="mb-1.5 block text-sm font-medium text-ink">AI Extraction Model</label>
              <select
                value={modelId}
                onChange={(e) => setModelId(e.target.value)}
                className="w-full rounded-lg border border-surface-border bg-surface-muted px-3 py-2.5 text-sm text-ink focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/20 transition-all"
              >
                {AVAILABLE_MODELS.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name} ({m.providerLabel})
                  </option>
                ))}
              </select>
            </div>
            
            <div className="w-full grid grid-cols-2 gap-3">
              <div>
                <label className="mb-1.5 block text-sm font-medium text-ink">Start Page</label>
                <input
                  id="start-page-input"
                  type="number"
                  min="1"
                  placeholder="e.g. 1"
                  value={startPage}
                  onChange={(e) => setStartPage(e.target.value)}
                  className="w-full rounded-lg border border-surface-border bg-surface-muted px-3 py-2.5 text-sm text-ink focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/20 transition-all placeholder:text-ink-muted/50"
                />
              </div>
              <div>
                <label className="mb-1.5 block text-sm font-medium text-ink">End Page</label>
                <input
                  id="end-page-input"
                  type="number"
                  min="1"
                  placeholder="e.g. 5"
                  value={endPage}
                  onChange={(e) => setEndPage(e.target.value)}
                  className="w-full rounded-lg border border-surface-border bg-surface-muted px-3 py-2.5 text-sm text-ink focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/20 transition-all placeholder:text-ink-muted/50"
                />
              </div>
            </div>
          </div>

          {pageRangeError && (
            <p className="text-sm text-red-400 flex items-center gap-1.5">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 flex-shrink-0" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
              </svg>
              {pageRangeError}
            </p>
          )}

          <Button
            onClick={handleUpload}
            disabled={files.length === 0 || state === STATES.UPLOADING || state === STATES.SUBMITTED || !!pageRangeError}
            loading={state === STATES.UPLOADING || state === STATES.SUBMITTED}
            className="w-full justify-center py-2.5"
          >
            {state === STATES.SUBMITTED ? 'Processing...' : 'Extract Content'}
          </Button>

          <UploadProgress state={state} error={error} STATES={STATES} />
        </div>
      </Card>

      {/* Stats Row */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3 animate-slide-up-fade" style={{ animationDelay: '300ms', animationFillMode: 'both' }}>
        <StatCard icon={FileUp} label="Total Jobs" value={total} color="text-indigo-400" />
        <StatCard icon={CheckCircle2} label="Completed" value={completed} color="text-emerald-400" />
        <StatCard icon={Clock} label="Processing" value={processing} color="text-amber-400" />
      </div>

      {/* Recent Jobs */}
      <div className="animate-slide-up-fade" style={{ animationDelay: '400ms', animationFillMode: 'both' }}>
        <h2 className="mb-4 text-lg font-semibold text-white/90">Recent Documents</h2>
        <JobTable
          jobs={recentJobs}
          onSelectJob={setSelectedJob}
          emptyAction={() => {}}
        />
      </div>

      {selectedJob && (
        <JobDetailPanel job={selectedJob} onClose={() => setSelectedJob(null)} />
      )}
    </div>
  )
}
