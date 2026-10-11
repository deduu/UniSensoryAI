export class ApiError extends Error {
  constructor(message, status, data) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.data = data
  }
}

// Event AuthContext listens for to clear local state and redirect on 401.
export const AUTH_EXPIRED_EVENT = 'auth:expired'

// Build-time API base URL. Empty in local dev (Vite proxies /v1/* to the
// backend); set to e.g. https://api.example.com on Cloudflare Pages when
// the SPA and API live on different subdomains.
export const API_BASE = (import.meta.env?.VITE_API_BASE || '').replace(/\/+$/, '')

/**
 * Fetch wrapper with timeout, base URL, and error handling.
 *
 * Sends credentials so the HttpOnly access_token cookie is included on
 * every API call. A 401 response dispatches an `auth:expired` event so
 * the AuthContext can route the user back to /login without each caller
 * handling it individually.
 */
export async function apiFetch(path, options = {}) {
  const { timeout = 30000, baseUrl = API_BASE, credentials = 'include', ...fetchOpts } = options

  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeout)

  try {
    const url = `${baseUrl}${path}`
    const response = await fetch(url, {
      ...fetchOpts,
      credentials,
      signal: controller.signal,
    })

    if (!response.ok) {
      if (response.status === 401) {
        window.dispatchEvent(new CustomEvent(AUTH_EXPIRED_EVENT))
      }
      let data = null
      try {
        data = await response.json()
      } catch {
        // ignore parse failures
      }
      throw new ApiError(
        data?.detail || `Request failed: ${response.status}`,
        response.status,
        data
      )
    }

    return await response.json()
  } catch (err) {
    if (err.name === 'AbortError') {
      throw new ApiError('Request timed out', 408)
    }
    if (err instanceof ApiError) throw err
    throw new ApiError(err.message, 0)
  } finally {
    clearTimeout(timer)
  }
}
