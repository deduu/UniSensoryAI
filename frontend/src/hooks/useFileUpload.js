import { useState, useCallback } from 'react'
import { uploadDocument } from '../api/jobs'
import { useApp } from '../context/AppContext'
import { useJobs } from '../context/JobContext'
import { useSettings } from '../context/SettingsContext'

const STATES = {
  IDLE: 'IDLE',
  FILES_SELECTED: 'FILES_SELECTED',
  UPLOADING: 'UPLOADING',
  SUBMITTED: 'SUBMITTED',
  DONE: 'DONE',
  ERROR: 'ERROR',
}

export function useFileUpload() {
  const { backendUrl } = useApp()
  const { addJob } = useJobs()
  const { apiKeys } = useSettings()
  const [files, setFiles] = useState([])
  const [state, setState] = useState(STATES.IDLE)
  const [error, setError] = useState(null)
  const [lastJobId, setLastJobId] = useState(null)

  const addFiles = useCallback((newFiles) => {
    setFiles((prev) => [...prev, ...Array.from(newFiles)])
    setState(STATES.FILES_SELECTED)
    setError(null)
  }, [])

  const removeFile = useCallback((index) => {
    setFiles((prev) => {
      const next = prev.filter((_, i) => i !== index)
      if (next.length === 0) setState(STATES.IDLE)
      return next
    })
  }, [])

  const upload = useCallback(
    async (modelId = 'qwen3-vl-30b', startPage = null, endPage = null) => {
      if (files.length === 0) return
      setState(STATES.UPLOADING)
      setError(null)

      try {
        // Upload first file (backend processes one at a time)
        const file = files[0]
        const result = await uploadDocument(file, modelId, backendUrl, apiKeys, startPage, endPage)
        setLastJobId(result.job_id)

        addJob({
          job_id: result.job_id,
          status: result.status,
          filename: file.name,
          fileSize: file.size,
          model_id: modelId,
          created_at: new Date().toISOString(),
          documents: [],
        })

        setState(STATES.SUBMITTED)

        // If multiple files, upload remaining sequentially
        for (let i = 1; i < files.length; i++) {
          const f = files[i]
          const r = await uploadDocument(f, modelId, backendUrl, apiKeys, startPage, endPage)
          addJob({
            job_id: r.job_id,
            status: r.status,
            filename: f.name,
            fileSize: f.size,
            model_id: modelId,
            created_at: new Date().toISOString(),
            documents: [],
          })
        }

        setState(STATES.DONE)
      } catch (err) {
        setError(err.message || 'Upload failed')
        setState(STATES.ERROR)
      }
    },
    [files, backendUrl, addJob, apiKeys]
  )

  const reset = useCallback(() => {
    setFiles([])
    setState(STATES.IDLE)
    setError(null)
    // lastJobId is intentionally kept so polling continues until the job reaches a terminal state
  }, [])

  return { files, state, error, lastJobId, addFiles, removeFile, upload, reset, STATES }
}
