import { useMemo } from 'react'
import { useApp } from '../context/AppContext'
import { useJobs } from '../context/JobContext'
import { createPaperApi } from '../api/paper'

/** Share the selected server and refresh history after accepted PAPER uploads or retries. */
export function usePaperApi() {
  const { backendUrl } = useApp()
  const { refreshJobs } = useJobs()
  return useMemo(() => createPaperApi(backendUrl, { onExtractionQueued: refreshJobs }), [backendUrl, refreshJobs])
}
