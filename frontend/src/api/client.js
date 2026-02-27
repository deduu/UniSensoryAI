export class ApiError extends Error {
  constructor(message, status, data) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.data = data
  }
}

/**
 * Fetch wrapper with timeout, base URL, and error handling.
 */
export async function apiFetch(path, options = {}) {
  const { timeout = 30000, baseUrl = '', ...fetchOpts } = options

  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeout)

  try {
    const url = `${baseUrl}${path}`
    const response = await fetch(url, {
      ...fetchOpts,
      signal: controller.signal,
    })

    if (!response.ok) {
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
