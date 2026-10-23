import {
  ChevronUp,
  ClipboardCheck,
  Files,
  History,
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
import { Link, useNavigate } from 'react-router-dom'
import SidebarItem from './SidebarItem'
import { useSettings } from '../../context/SettingsContext'
import { useAuth } from '../../context/AuthContext'

const NAV_ITEMS = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/paper', icon: ClipboardCheck, label: 'PAPER review' },
  { to: '/uploads', icon: History, label: 'Upload history' },
  { to: '/documents', icon: Files, label: 'Documents' },
  { to: '/chat', icon: MessageSquare, label: 'Chat' },
  { to: '/models', icon: Cpu, label: 'Models' },
]

export default function Sidebar() {
  const [accountOpen, setAccountOpen] = useState(false)
  const accountRef = useRef(null)
  const { theme, toggleTheme } = useSettings()
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const isDark = theme === 'dark'
  const sharedDemo = import.meta.env.VITE_SHARED_DEMO === 'true'

  const handleLogout = async () => {
    setAccountOpen(false)
    await logout()
    navigate('/login', { replace: true })
  }

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
    <aside className="fixed inset-y-0 left-0 z-30 flex w-16 flex-col bg-surface-glass backdrop-blur-xl transition-all duration-300 md:w-64">
      <div className="flex h-16 items-center justify-center gap-3 bg-surface/20 px-2 md:justify-start md:px-5">
        <div title="Intelidoc" className="relative flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-brand to-cyan-400 text-white font-bold text-sm shadow-[0_0_15px_rgba(99,102,241,0.5)]">
          I
          <div className="absolute inset-0 rounded-xl bg-white/20 blur-sm mix-blend-overlay" />
        </div>
        <span className="hidden text-lg font-bold text-ink tracking-tight md:inline">
          Intelidoc
        </span>
      </div>

      <nav aria-label="Main navigation" className="flex-1 space-y-1.5 overflow-y-auto px-2 py-6 md:px-3">
        {NAV_ITEMS.map((item) => (
          <SidebarItem key={item.to} {...item} />
        ))}
      </nav>

      <div ref={accountRef} className="relative bg-surface/30 p-2 backdrop-blur-sm md:p-3">
        {accountOpen && (
          <div className="absolute bottom-full left-2 mb-2 w-56 max-w-[calc(100vw-1rem)] overflow-hidden rounded-xl border border-surface-border bg-surface shadow-card md:left-3 md:right-3 md:w-auto">
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
              {sharedDemo ? (
                <p className="px-3 py-2 text-xs text-ink-faint">
                  Shared demo. Close your private browser window when finished.
                </p>
              ) : (
                <button
                  type="button"
                  onClick={handleLogout}
                  className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-ink-muted transition-colors hover:bg-surface-subtle hover:text-ink"
                >
                  <LogOut className="h-4 w-4" />
                  Sign out
                </button>
              )}
            </div>
          </div>
        )}

        <button
          type="button"
          aria-expanded={accountOpen}
          aria-label="Open account menu"
          title="Open account menu"
          onClick={() => setAccountOpen((open) => !open)}
          className="flex w-full items-center justify-center gap-3 rounded-xl px-0 py-2.5 text-left transition-colors hover:bg-surface-subtle md:justify-start md:px-2"
        >
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-brand/80 to-cyan-500/80 text-white select-none">
            <User className="h-4 w-4" />
          </div>
          <div className="hidden min-w-0 flex-1 md:block">
            <p className="text-sm font-medium text-ink truncate">
              {user?.email || user?.user_id || 'My Account'}
            </p>
            <p className="mt-0.5 truncate text-[11px] text-ink-faint">Settings and session</p>
          </div>
          <ChevronUp className={`hidden h-4 w-4 shrink-0 text-ink-faint transition-transform md:block ${accountOpen ? 'rotate-180' : ''}`} />
        </button>
      </div>
    </aside>
  )
}
