import { Outlet, useLocation } from 'react-router-dom'
import Sidebar from './Sidebar'
import { useBackendHealth } from '../../hooks/useBackendHealth'
import { useJobList } from '../../hooks/useJobList'
import { useAuth } from '../../context/AuthContext'
import { useApp } from '../../context/AppContext'
import { jobScope } from '../../jobs/history'

export default function AppShell() {
  const location = useLocation()
  const { user } = useAuth()
  const { backendUrl } = useApp()
  useBackendHealth()
  const { historyError, historyLoading, refreshAll } = useJobList()

  return (
    <div className="flex min-h-screen mesh-bg animate-fade-in text-ink selection:bg-brand selection:text-white">
      <Sidebar />
      <div className="relative z-10 flex min-w-0 flex-1 flex-col pl-16 md:pl-64">
        <main className={`w-full min-w-0 flex-1 ${location.pathname.startsWith('/chat') ? '' : 'p-3 sm:p-8'}`}>
          {historyError && <div role="alert" className="mb-4 rounded-lg border border-red-500/20 bg-red-500/5 p-3 text-sm text-red-600 dark:text-red-400">Saved upload history could not be refreshed. {historyError} <button type="button" className="underline" disabled={historyLoading} onClick={refreshAll}>Retry history</button></div>}
          <Outlet key={jobScope(user, backendUrl)} />
        </main>
      </div>
    </div>
  )
}
