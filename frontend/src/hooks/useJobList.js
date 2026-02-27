import { useEffect, useCallback, useRef } from 'react'
import { listJobs, getJob } from '../api/jobs'
import { useApp } from '../context/AppContext'
import { useJobs } from '../context/JobContext'

/**
 * Extract clean filename from a file path.
 * Handles Windows backslashes and strips UUID prefix (e.g. "abc123_file.pdf" → "file.pdf").
 */
function extractFilename(filePath) {
  if (!filePath) return null
  // Split on both / and \ for cross-platform support
  const basename = filePath.split(/[/\\]/).pop() || ''
  // Strip UUID prefix: pattern is 8-4-4-4-12 hex chars followed by _
  return basename.replace(/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}_/, '')
}

/**
 * On mount, fetch all jobs from backend and merge with session state.
 * Also refresh non-terminal jobs to get latest status.
 */
export function useJobList() {
  const { backendUrl, connectionStatus } = useApp()
  const { jobs, updateJob, addJob, setAllJobs } = useJobs()
  const hasFetched = useRef(false)

  // Fetch all jobs from backend on first mount
  useEffect(() => {
    if (hasFetched.current || connectionStatus !== 'healthy') return
    hasFetched.current = true

    async function fetchFromBackend() {
      try {
        const backendJobs = await listJobs(backendUrl)
        if (!Array.isArray(backendJobs) || backendJobs.length === 0) return

        // Build a set of existing job IDs for dedup
        const existingIds = new Set(jobs.map((j) => j.job_id))

        // Map backend jobs to frontend shape and merge
        const mapped = backendJobs.map((bj) => ({
          job_id: bj.job_id,
          status: bj.status?.toLowerCase(),
          filename: extractFilename(bj.file_path) || bj.job_id,
          model_id: bj.meta?.model_id || '—',
          created_at: bj.created_at,
          updated_at: bj.updated_at,
          documents: bj.documents || [],
          meta: bj.meta,
        }))

        // Merge: keep session jobs, add any backend-only jobs
        const newJobs = mapped.filter((j) => !existingIds.has(j.job_id))
        if (newJobs.length > 0) {
          // Update existing jobs with latest backend data, then add new ones
          const mergedIds = new Set()
          const merged = jobs.map((sessionJob) => {
            const backendMatch = mapped.find((bj) => bj.job_id === sessionJob.job_id)
            mergedIds.add(sessionJob.job_id)
            return backendMatch ? { ...sessionJob, ...backendMatch } : sessionJob
          })
          // Add jobs only in backend
          const backendOnly = mapped.filter((bj) => !mergedIds.has(bj.job_id))
          setAllJobs([...merged, ...backendOnly])
        } else {
          // Just update existing jobs with backend data
          mapped.forEach((bj) => {
            if (existingIds.has(bj.job_id)) {
              updateJob(bj.job_id, bj)
            }
          })
        }
      } catch {
        // Backend unavailable — fall back to session-only jobs
      }
    }

    fetchFromBackend()
  }, [connectionStatus]) // eslint-disable-line react-hooks/exhaustive-deps

  const refreshAll = useCallback(async () => {
    const pending = jobs.filter(
      (j) => j.status !== 'completed' && j.status !== 'failed'
    )

    const results = await Promise.allSettled(
      pending.map((j) => getJob(j.job_id, backendUrl))
    )

    results.forEach((result, i) => {
      if (result.status === 'fulfilled') {
        const data = result.value
        updateJob(pending[i].job_id, {
          status: data.status?.toLowerCase(),
          documents: data.documents || [],
          updated_at: data.updated_at,
        })
      }
    })
  }, [jobs, backendUrl, updateJob])

  useEffect(() => {
    if (jobs.length > 0) {
      refreshAll()
    }
  }, []) // only on mount

  return { jobs, refreshAll }
}
