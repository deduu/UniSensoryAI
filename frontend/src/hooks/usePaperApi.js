import { useMemo } from 'react'
import { useApp } from '../context/AppContext'
import { useJobs } from '../context/JobContext'
import { createPaperApi } from '../api/paper'

/** Share the selected server and refresh history after accepted extraction changes. */
export function usePaperApi() {
  const { backendUrl } = useApp()
  const { refreshJobs } = useJobs()
  return useMemo(() => createPaperApi(backendUrl, { onExtractionQueued: refreshJobs, onExtractionChanged: refreshJobs }), [backendUrl, refreshJobs])
}
