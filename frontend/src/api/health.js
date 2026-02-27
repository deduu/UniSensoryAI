import { apiFetch, ApiError } from './client'

/**
 * Ping the backend root endpoint and measure latency.
 * Returns { healthy: boolean, latency: number|null, error: string|null }
 */
export async function checkHealth(baseUrl = '') {
  const start = performance.now()
  try {
    const data = await apiFetch('/health', { baseUrl, timeout: 5000 })
    const latency = Math.round(performance.now() - start)
    return {
      healthy: data.status === 'healthy',
      latency,
      error: null,
    }
  } catch (err) {
    return {
      healthy: false,
      latency: null,
      error: err instanceof ApiError ? err.message : 'Connection failed',
    }
  }
}
