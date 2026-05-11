import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import { AppProvider } from './context/AppContext'
import { JobProvider } from './context/JobContext'
import { SettingsProvider } from './context/SettingsContext'
import { ToastProvider } from './context/ToastContext'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <AppProvider>
        <SettingsProvider>
          <JobProvider>
            <ToastProvider>
              <App />
            </ToastProvider>
          </JobProvider>
        </SettingsProvider>
      </AppProvider>
    </BrowserRouter>
  </React.StrictMode>
)
