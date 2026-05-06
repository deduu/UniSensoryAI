import React, { createContext, useContext, useState, useEffect } from 'react'

const SettingsContext = createContext()

export function SettingsProvider({ children }) {
  const [apiKeys, setApiKeys] = useState(() => {
    try {
      const saved = localStorage.getItem('unisensory_api_keys')
      return saved ? JSON.parse(saved) : { OPENAI_API_KEY: '', OPENAI_API_BASE: '', GOOGLE_API_KEY: '' }
    } catch (e) {
      return { OPENAI_API_KEY: '', OPENAI_API_BASE: '', GOOGLE_API_KEY: '' }
    }
  })

  useEffect(() => {
    localStorage.setItem('unisensory_api_keys', JSON.stringify(apiKeys))
  }, [apiKeys])

  const updateApiKey = (provider, key) => {
    setApiKeys((prev) => ({
      ...prev,
      [provider]: key,
    }))
  }

  return (
    <SettingsContext.Provider value={{ apiKeys, updateApiKey }}>
      {children}
    </SettingsContext.Provider>
  )
}

export function useSettings() {
  return useContext(SettingsContext)
}
