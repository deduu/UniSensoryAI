import { useState, useEffect, useCallback, useRef } from 'react'
import { checkHealth } from '../api/health'
import { useApp } from '../context/AppContext'

/**
 * Ping backend every `interval` ms.
 * Returns { status, latency, lastChecked, check }
 */
export function useBackendHealth(interval = 30000) {
  const { backendUrl, setConnectionStatus } = useApp()
  const [state, setState] = useState({
    status: 'unknown',
    latency: null,
    lastChecked: null,
    error: null,
  })
  const intervalRef = useRef(null)

  const check = useCallback(async () => {
    const result = await checkHealth(backendUrl)
    const status = result.healthy ? 'healthy' : 'unhealthy'
    setState({
      status,
      latency: result.latency,
      lastChecked: new Date(),
      error: result.error,
    })
    setConnectionStatus(status)
  }, [backendUrl, setConnectionStatus])

  useEffect(() => {
    check()
    intervalRef.current = setInterval(check, interval)
    return () => clearInterval(intervalRef.current)
  }, [check, interval])

  return { ...state, check }
}
