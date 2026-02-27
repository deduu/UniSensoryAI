import { createContext, useContext, useState, useCallback } from 'react'

const AppContext = createContext(null)

export function AppProvider({ children }) {
  const [backendUrl, setBackendUrl] = useState(
    () => localStorage.getItem('unisensory_backend_url') || ''
  )
  const [connectionStatus, setConnectionStatus] = useState('unknown') // unknown | healthy | unhealthy

  const updateBackendUrl = useCallback((url) => {
    const cleaned = url.replace(/\/+$/, '')
    setBackendUrl(cleaned)
    localStorage.setItem('unisensory_backend_url', cleaned)
  }, [])

  return (
    <AppContext.Provider
      value={{
        backendUrl,
        setBackendUrl: updateBackendUrl,
        connectionStatus,
        setConnectionStatus,
      }}
    >
      {children}
    </AppContext.Provider>
  )
}

export function useApp() {
  const ctx = useContext(AppContext)
  if (!ctx) throw new Error('useApp must be used within AppProvider')
  return ctx
}
