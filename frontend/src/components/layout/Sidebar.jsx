import {
  ChevronUp,
  Cpu,
  LayoutDashboard,
  LogOut,
  MessageSquare,
  Moon,
  Settings,
  Sun,
  User,
} from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import SidebarItem from './SidebarItem'
import { useSettings } from '../../context/SettingsContext'

const NAV_ITEMS = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/chat', icon: MessageSquare, label: 'Chat' },
  { to: '/models', icon: Cpu, label: 'Models' },
]

export default function Sidebar() {
  const [accountOpen, setAccountOpen] = useState(false)
  const accountRef = useRef(null)
  const { theme, toggleTheme } = useSettings()
  const isDark = theme === 'dark'

  useEffect(() => {
    if (!accountOpen) return undefined

    const handlePointerDown = (event) => {
      if (!accountRef.current?.contains(event.target)) setAccountOpen(false)
    }
    const handleKeyDown = (event) => {
      if (event.key === 'Escape') setAccountOpen(false)
    }

    document.addEventListener('mousedown', handlePointerDown)
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('mousedown', handlePointerDown)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [accountOpen])

  return (
    <aside className="fixed inset-y-0 left-0 z-30 flex w-64 flex-col bg-surface-glass backdrop-blur-xl transition-all duration-300">
      <div className="flex h-16 items-center gap-3 px-5 bg-surface/20">
        <div className="relative flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-br from-brand to-cyan-400 text-white font-bold text-sm shadow-[0_0_15px_rgba(99,102,241,0.5)]">
          I
          <div className="absolute inset-0 rounded-xl bg-white/20 blur-sm mix-blend-overlay" />
        </div>
        <span className="text-lg font-bold text-ink tracking-tight">
          Intelidoc
        </span>
      </div>

      <nav className="flex-1 space-y-1.5 overflow-y-auto px-3 py-6">
        {NAV_ITEMS.map((item) => (
          <SidebarItem key={item.to} {...item} />
        ))}
      </nav>

      <div ref={accountRef} className="relative bg-surface/30 p-3 backdrop-blur-sm">
        {accountOpen && (
          <div className="absolute bottom-full left-3 right-3 mb-2 overflow-hidden rounded-xl border border-surface-border bg-surface shadow-card">
            <div className="px-3 py-3">
              <p className="text-xs font-semibold text-ink">My Account</p>
              <p className="mt-1 text-[11px] text-ink-faint">Account actions</p>
            </div>
            <div className="border-t border-surface-border/70 p-1.5">
              <button
                type="button"
                onClick={() => { toggleTheme(); setAccountOpen(false) }}
                className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-ink-muted transition-colors hover:bg-surface-subtle hover:text-ink"
              >
                {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
                {isDark ? 'Light mode' : 'Dark mode'}
              </button>
              <Link
                to="/settings"
                onClick={() => setAccountOpen(false)}
                className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-ink-muted transition-colors hover:bg-surface-subtle hover:text-ink"
              >
                <Settings className="h-4 w-4" />
                Settings
              </Link>
              <button
                type="button"
                onClick={() => setAccountOpen(false)}
                className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-ink-muted transition-colors hover:bg-surface-subtle hover:text-ink"
              >
                <LogOut className="h-4 w-4" />
                Sign out
              </button>
            </div>
          </div>
        )}

        <button
          type="button"
          aria-expanded={accountOpen}
          aria-label="Open account menu"
          onClick={() => setAccountOpen((open) => !open)}
          className="flex w-full items-center gap-3 rounded-xl px-2 py-2.5 text-left transition-colors hover:bg-surface-subtle"
        >
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-brand/80 to-cyan-500/80 text-white select-none">
            <User className="h-4 w-4" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-ink truncate">My Account</p>
            <p className="mt-0.5 truncate text-[11px] text-ink-faint">Settings and session</p>
          </div>
          <ChevronUp className={`h-4 w-4 shrink-0 text-ink-faint transition-transform ${accountOpen ? 'rotate-180' : ''}`} />
        </button>
      </div>
    </aside>
  )
}
