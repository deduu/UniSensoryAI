import {
  LayoutDashboard,
  FileUp,
  FileText,
  FlaskConical,
  MessageSquare,
  Cpu,
  Settings,
} from 'lucide-react'
import SidebarItem from './SidebarItem'
import { useApp } from '../../context/AppContext'

const NAV_ITEMS = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/parse', icon: FileUp, label: 'Parse' },
  { to: '/documents', icon: FileText, label: 'Documents' },
  { to: '/playground', icon: FlaskConical, label: 'Playground' },
  { to: '/chat', icon: MessageSquare, label: 'Chat' },
  { to: '/models', icon: Cpu, label: 'Models' },
  { to: '/settings', icon: Settings, label: 'Settings' },
]

export default function Sidebar() {
  const { connectionStatus } = useApp()

  return (
    <aside className="fixed inset-y-0 left-0 z-30 flex w-60 flex-col bg-sidebar-bg">
      {/* Logo */}
      <div className="flex h-16 items-center gap-3 px-5">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand text-white font-bold text-sm">
          U
        </div>
        <span className="text-lg font-semibold text-white">UniSensoryAI</span>
      </div>

      {/* Nav */}
      <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
        {NAV_ITEMS.map((item) => (
          <SidebarItem key={item.to} {...item} />
        ))}
      </nav>

      {/* Connection Status */}
      <div className="border-t border-white/10 px-5 py-3">
        <div className="flex items-center gap-2 text-xs text-sidebar-text">
          <span
            className={`h-2 w-2 rounded-full ${
              connectionStatus === 'healthy'
                ? 'bg-emerald-400'
                : connectionStatus === 'unhealthy'
                  ? 'bg-red-400'
                  : 'bg-gray-500'
            }`}
          />
          <span>
            {connectionStatus === 'healthy'
              ? 'Backend Connected'
              : connectionStatus === 'unhealthy'
                ? 'Backend Offline'
                : 'Checking...'}
          </span>
        </div>
      </div>
    </aside>
  )
}
