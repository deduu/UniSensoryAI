import { Outlet, useLocation } from 'react-router-dom'
import Sidebar from './Sidebar'
import TopBar from './TopBar'
import { useBackendHealth } from '../../hooks/useBackendHealth'

export default function AppShell() {
  const location = useLocation()
  // Start health polling at the shell level
  useBackendHealth()

  return (
    <div className="flex min-h-screen mesh-bg animate-fade-in text-ink selection:bg-brand selection:text-white">
      <Sidebar />
      <div className="flex flex-1 flex-col pl-60 relative z-10 min-w-0">
        <TopBar />
        <main className={`flex-1 min-w-0 ${location.pathname.startsWith('/chat') ? '' : 'p-8'}`}>
          <Outlet />
        </main>
      </div>
    </div>
  )
}
