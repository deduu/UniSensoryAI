import { Outlet, useLocation } from 'react-router-dom'
import Sidebar from './Sidebar'
import { useBackendHealth } from '../../hooks/useBackendHealth'
import { useJobList } from '../../hooks/useJobList'

export default function AppShell() {
  const location = useLocation()
  useBackendHealth()
  useJobList() // Fetch jobs once authenticated

  return (
    <div className="flex min-h-screen mesh-bg animate-fade-in text-ink selection:bg-brand selection:text-white">
      <Sidebar />
      <div className="flex flex-1 flex-col pl-64 relative z-10 min-w-0">
        <main className={`flex-1 min-w-0 ${location.pathname.startsWith('/chat') ? '' : 'p-8'}`}>
          <Outlet />
        </main>
      </div>
    </div>
  )
}
