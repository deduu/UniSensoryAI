import { useJobs } from '../context/JobContext'

/** The shared provider hydrates persisted history and polls every active upload. */
export function useJobList() {
  const { jobs, refreshJobs, historyLoading, historyError } = useJobs()
  return { jobs, refreshAll: refreshJobs, historyLoading, historyError }
}
