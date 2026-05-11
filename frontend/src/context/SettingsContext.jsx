import React, { createContext, useContext, useState, useEffect, useCallback } from 'react'

const SettingsContext = createContext()

const THEME_KEY = 'unisensory_theme'
const VALID_THEMES = ['light', 'dark']

function readInitialTheme() {
  try {
    const t = localStorage.getItem(THEME_KEY)
    return VALID_THEMES.includes(t) ? t : 'light'
  } catch (e) {
    return 'light'
  }
}

function applyThemeClass(theme) {
  const root = document.documentElement
  if (theme === 'dark') root.classList.add('dark')
  else root.classList.remove('dark')
}

export function SettingsProvider({ children }) {
  const [apiKeys, setApiKeys] = useState(() => {
    try {
      const saved = localStorage.getItem('unisensory_api_keys')
      return saved ? JSON.parse(saved) : { OPENAI_API_KEY: '', OPENAI_API_BASE: '', GOOGLE_API_KEY: '' }
    } catch (e) {
      return { OPENAI_API_KEY: '', OPENAI_API_BASE: '', GOOGLE_API_KEY: '' }
    }
  })

  const [theme, setThemeState] = useState(readInitialTheme)

  useEffect(() => {
    localStorage.setItem('unisensory_api_keys', JSON.stringify(apiKeys))
  }, [apiKeys])

  // Reflect theme on <html> + persist. The inline script in index.html applies
  // the persisted theme before React mounts to prevent FOUC; this effect keeps
  // the class in sync after toggles.
  useEffect(() => {
    applyThemeClass(theme)
    try {
      localStorage.setItem(THEME_KEY, theme)
    } catch (e) { /* ignore */ }
  }, [theme])

  const setTheme = useCallback((next) => {
    if (VALID_THEMES.includes(next)) setThemeState(next)
  }, [])

  const toggleTheme = useCallback(() => {
    setThemeState((prev) => (prev === 'dark' ? 'light' : 'dark'))
  }, [])

  const updateApiKey = (provider, key) => {
    setApiKeys((prev) => ({
      ...prev,
      [provider]: key,
    }))
  }

  return (
    <SettingsContext.Provider value={{ apiKeys, updateApiKey, theme, setTheme, toggleTheme }}>
      {children}
    </SettingsContext.Provider>
  )
}

export function useSettings() {
  return useContext(SettingsContext)
}
