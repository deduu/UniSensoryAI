import { createContext, useContext, useState, useCallback, useEffect, useRef } from 'react'
import { useAuth } from './AuthContext'
import { useApp } from './AppContext'
import { getJob as fetchJob, listJobs } from '../api/jobs'
import { jobScope, jobsForScope, normalizeHistoryJob, discardLegacyJobCache, reconcileHistorySnapshot } from '../jobs/history'

const JobContext = createContext(null)

/** Server-backed history scoped to the current authenticated tenant and API host. */
export function JobProvider({ children }) {
  const { user } = useAuth()
  const { backendUrl, connectionStatus } = useApp()
  const scope = jobScope(user, backendUrl)
  const currentScope = useRef(scope)
  currentScope.current = scope
  const request = useRef(0)
  const mutations = useRef({ scope, sequence: 0, added: new Map(), removed: new Set() })
  if (mutations.current.scope !== scope) mutations.current = { scope, sequence: 0, added: new Map(), removed: new Set() }
  const [state, setState] = useState({ scope: null, jobs: [], loading: false, error: '' })
  const jobs = jobsForScope(state, scope)

  useEffect(() => { discardLegacyJobCache() }, [])

  const patch = useCallback(transform => {
    if (!scope || currentScope.current !== scope) return
    setState(previous => previous.scope === scope ? { ...previous, jobs: transform(previous.jobs) } : previous)
  }, [scope])
  const addJob = useCallback(job => {
    if (currentScope.current !== scope) return
    mutations.current.added.set(job.job_id, ++mutations.current.sequence)
    mutations.current.removed.delete(job.job_id)
    patch(previous => [normalizeHistoryJob(job), ...previous.filter(item => item.job_id !== job.job_id)])
  }, [patch, scope])
  const updateJob = useCallback((id, updates) => patch(previous => previous.map(job => job.job_id === id ? normalizeHistoryJob({ ...job, ...updates }) : job)), [patch])
  const removeJob = useCallback(id => {
    if (currentScope.current !== scope) return
    mutations.current.removed.add(id)
    mutations.current.added.delete(id)
    patch(previous => previous.filter(job => job.job_id !== id))
  }, [patch, scope])
  const setAllJobs = useCallback(value => patch(() => value.map(normalizeHistoryJob)), [patch])
  const getJob = useCallback(id => jobs.find(job => job.job_id === id) || null, [jobs])

  const refreshJobs = useCallback(async () => {
    if (!scope || currentScope.current !== scope) return
    const sequence = ++request.current
    const mutationSequence = mutations.current.sequence
    setState(previous => ({ scope, jobs: jobsForScope(previous, scope), loading: true, error: '' }))
    try {
      const records = []
      let offset = 0
      while (currentScope.current === scope && sequence === request.current) {
        const page = await listJobs(backendUrl, 200, offset)
        if (!Array.isArray(page)) throw new Error('Unable to read saved upload history.')
        records.push(...page.map(normalizeHistoryJob))
        if (page.length < 200) break
        offset += 200
      }
      if (currentScope.current === scope && sequence === request.current) {
        const added = new Set([...mutations.current.added].filter(([, value]) => value > mutationSequence).map(([id]) => id))
        setState(previous => ({ scope, jobs: reconcileHistorySnapshot(jobsForScope(previous, scope), records, added, mutations.current.removed), loading: false, error: '' }))
      }
    } catch (error) {
      if (currentScope.current === scope && sequence === request.current) setState(previous => ({ scope, jobs: jobsForScope(previous, scope), loading: false, error: error.message || 'Unable to load saved uploads.' }))
    }
  }, [scope, backendUrl])

  useEffect(() => {
    ++request.current
    setState({ scope, jobs: [], loading: false, error: '' })
    return () => { ++request.current }
  }, [scope])

  useEffect(() => {
    if (scope && connectionStatus === 'healthy') refreshJobs()
  }, [scope, connectionStatus, refreshJobs])

  useEffect(() => {
    const pending = jobs.filter(job => !['completed', 'failed'].includes(job.status))
    if (!scope || !pending.length) return undefined
    let cancelled = false
    let running = false
    const timer = setInterval(async () => {
      if (running) return
      running = true
      const results = await Promise.allSettled(pending.map(job => fetchJob(job.job_id, backendUrl)))
      running = false
      if (cancelled || currentScope.current !== scope) return
      results.forEach(result => { if (result.status === 'fulfilled') updateJob(result.value.job_id, result.value) })
    }, 3000)
    return () => { cancelled = true; clearInterval(timer) }
  }, [jobs, scope, backendUrl, updateJob])

  return <JobContext.Provider value={{ jobs, addJob, updateJob, removeJob, setAllJobs, getJob, refreshJobs, historyLoading: state.scope === scope && state.loading, historyError: state.scope === scope ? state.error : '' }}>{children}</JobContext.Provider>
}

export function useJobs() {
  const context = useContext(JobContext)
  if (!context) throw new Error('useJobs must be used within JobProvider')
  return context
}
