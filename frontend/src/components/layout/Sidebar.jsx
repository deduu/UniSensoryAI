import {
  LayoutDashboard,
  FileText,
  MessageSquare,
  Cpu,
  Settings,
} from 'lucide-react'
import SidebarItem from './SidebarItem'
import { useApp } from '../../context/AppContext'

const NAV_ITEMS = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/documents', icon: FileText, label: 'Documents' },
  { to: '/chat', icon: MessageSquare, label: 'Chat' },
  { to: '/models', icon: Cpu, label: 'Models' },
  { to: '/settings', icon: Settings, label: 'Settings' },
]

export default function Sidebar() {
  const { connectionStatus } = useApp()

  return (
    <aside className="fixed inset-y-0 left-0 z-30 flex w-60 flex-col bg-surface-glass backdrop-blur-xl border-r border-surface-border transition-all duration-300">
      {/* Logo */}
      <div className="flex h-16 items-center gap-3 px-5 border-b border-surface-border/50">
        <div className="relative flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-br from-brand to-cyan-400 text-white font-bold text-sm shadow-[0_0_15px_rgba(99,102,241,0.5)]">
          U
          <div className="absolute inset-0 rounded-xl bg-white/20 blur-sm mix-blend-overlay"></div>
        </div>
        <span className="text-lg font-bold text-transparent bg-clip-text bg-gradient-to-r from-white to-white/70 tracking-tight">UniSensoryAI</span>
      </div>

      {/* Nav */}
      <nav className="flex-1 space-y-1.5 overflow-y-auto px-3 py-6">
        {NAV_ITEMS.map((item) => (
          <SidebarItem key={item.to} {...item} />
        ))}
      </nav>

      {/* Connection Status */}
      <div className="border-t border-surface-border/50 bg-surface/30 px-5 py-4 backdrop-blur-sm">
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
