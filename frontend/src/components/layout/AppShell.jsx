import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import TopBar from './TopBar'
import { useBackendHealth } from '../../hooks/useBackendHealth'

export default function AppShell() {
  // Start health polling at the shell level
  useBackendHealth()

  return (
    <div className="flex min-h-screen bg-surface-muted">
      <Sidebar />
      <div className="flex flex-1 flex-col pl-60">
        <TopBar />
        <main className="flex-1 p-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
