import { useEffect, useRef } from 'react'
import { getJob } from '../api/jobs'
import { useApp } from '../context/AppContext'
import { useJobs } from '../context/JobContext'

/**
 * Poll a specific job every `interval` ms until it reaches a terminal state.
 */
export function useJobPolling(jobId, interval = 2000) {
  const { backendUrl } = useApp()
  const { updateJob } = useJobs()
  const timerRef = useRef(null)

  useEffect(() => {
    if (!jobId) return

    let active = true

    async function poll() {
      try {
        const data = await getJob(jobId, backendUrl)
        if (!active) return

        // Status is already normalized to lowercase by the API layer (jobs.js)
        updateJob(jobId, {
          status: data.status,
          documents: data.documents || [],
          updated_at: data.updated_at,
          meta: data.meta,
        })

        const terminal = ['completed', 'failed']
        if (terminal.includes(data.status)) {
          return // stop polling
        }
      } catch {
        // continue polling on transient errors
      }

      if (active) {
        timerRef.current = setTimeout(poll, interval)
      }
    }

    poll()

    return () => {
      active = false
      clearTimeout(timerRef.current)
    }
  }, [jobId, backendUrl, interval, updateJob])
}
