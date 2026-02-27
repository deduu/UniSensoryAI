import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { FileUp, FlaskConical, FileText, CheckCircle2, Clock } from 'lucide-react'
import Card from '../components/ui/Card'
import JobTable from '../components/jobs/JobTable'
import JobDetailPanel from '../components/jobs/JobDetailPanel'
import { useJobs } from '../context/JobContext'
import { useApp } from '../context/AppContext'

function StatCard({ icon: Icon, label, value, color = 'text-brand' }) {
  return (
    <Card className="flex items-center gap-4 p-5">
      <div className={`flex h-12 w-12 items-center justify-center rounded-xl bg-brand-light ${color}`}>
        <Icon className="h-6 w-6" />
      </div>
      <div>
        <p className="text-2xl font-bold text-ink">{value}</p>
        <p className="text-sm text-ink-muted">{label}</p>
      </div>
    </Card>
  )
}

export default function Dashboard() {
  const { jobs } = useJobs()
  const { connectionStatus } = useApp()
  const navigate = useNavigate()
  const [selectedJob, setSelectedJob] = useState(null)

  useEffect(() => {
    document.title = 'Dashboard — UniSensoryAI'
  }, [])

  const total = jobs.length
  const completed = jobs.filter((j) => j.status === 'completed').length
  const processing = jobs.filter(
    (j) => j.status === 'processing' || j.status === 'queued' || j.status === 'pending'
  ).length
  const docCount = jobs.reduce((sum, j) => sum + (j.documents?.length || 0), 0)

  const recentJobs = jobs.slice(0, 10)

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-ink">Dashboard</h1>
        <p className="mt-1 text-sm text-ink-muted">
          Overview of your document processing pipeline
        </p>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard icon={FileUp} label="Total Jobs" value={total} />
        <StatCard icon={CheckCircle2} label="Completed" value={completed} />
        <StatCard icon={Clock} label="Processing" value={processing} />
        <StatCard icon={FileText} label="Documents" value={docCount} />
      </div>

      {/* Recent Jobs */}
      <div>
        <h2 className="mb-4 text-lg font-semibold text-ink">Recent Jobs</h2>
        <JobTable
          jobs={recentJobs}
          onSelectJob={setSelectedJob}
          emptyAction={() => navigate('/parse')}
        />
      </div>

      {selectedJob && (
        <JobDetailPanel job={selectedJob} onClose={() => setSelectedJob(null)} />
      )}

      {/* Quick Actions */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Card
          hover
          className="cursor-pointer p-6"
          onClick={() => navigate('/parse')}
        >
          <div className="flex items-center gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-brand-light">
              <FileUp className="h-6 w-6 text-brand" />
            </div>
            <div>
              <h3 className="font-semibold text-ink">Upload Document</h3>
              <p className="text-sm text-ink-muted">Parse a new document with AI</p>
            </div>
          </div>
        </Card>

        <Card
          hover
          className="cursor-pointer p-6"
          onClick={() => navigate('/playground')}
        >
          <div className="flex items-center gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-brand-light">
              <FlaskConical className="h-6 w-6 text-brand" />
            </div>
            <div>
              <h3 className="font-semibold text-ink">Playground</h3>
              <p className="text-sm text-ink-muted">Test models interactively</p>
            </div>
          </div>
        </Card>
      </div>
    </div>
  )
}
