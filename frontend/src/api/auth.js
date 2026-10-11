import { API_BASE, apiFetch } from './client'

export function getCurrentUser() {
  return apiFetch('/v1/auth/me')
}

export function logout() {
  return apiFetch('/v1/auth/logout', { method: 'POST' })
}

export function loginUrl(provider) {
  // Must be an absolute URL when the SPA and API live on different
  // origins, otherwise the browser would navigate to the SPA host.
  return `${API_BASE}/v1/auth/login/${provider}`
}
