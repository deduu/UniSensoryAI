import { createContext, useContext, useState, useCallback, useEffect } from 'react'

const JobContext = createContext(null)

const STORAGE_KEY = 'unisensory_jobs'

function loadJobs() {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

function saveJobs(jobs) {
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(jobs))
}

export function JobProvider({ children }) {
  const [jobs, setJobs] = useState(loadJobs)

  useEffect(() => {
    saveJobs(jobs)
  }, [jobs])

  const addJob = useCallback((job) => {
    setJobs((prev) => [job, ...prev])
  }, [])

  const updateJob = useCallback((jobId, updates) => {
    setJobs((prev) =>
      prev.map((j) => (j.job_id === jobId ? { ...j, ...updates } : j))
    )
  }, [])

  const removeJob = useCallback((jobId) => {
    setJobs((prev) => prev.filter((j) => j.job_id !== jobId))
  }, [])

  const setAllJobs = useCallback((newJobs) => {
    setJobs(newJobs)
  }, [])

  const getJob = useCallback(
    (jobId) => jobs.find((j) => j.job_id === jobId) || null,
    [jobs]
  )

  return (
    <JobContext.Provider value={{ jobs, addJob, updateJob, removeJob, setAllJobs, getJob }}>
      {children}
    </JobContext.Provider>
  )
}

export function useJobs() {
  const ctx = useContext(JobContext)
  if (!ctx) throw new Error('useJobs must be used within JobProvider')
  return ctx
}
