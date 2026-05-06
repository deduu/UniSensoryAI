import { useLocation, Link } from 'react-router-dom'
import { ChevronRight } from 'lucide-react'

const PAGE_TITLES = {
  '/': 'Dashboard',
  '/parse': 'Parse Documents',
  '/documents': 'Documents',
  '/playground': 'Playground',
  '/chat': 'Chat',
  '/models': 'Models',
  '/settings': 'Settings',
}

export default function TopBar() {
  const { pathname } = useLocation()
  const title = PAGE_TITLES[pathname] || 'UniSensoryAI'

  return (
    <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b border-surface-border/50 bg-surface/30 px-8 backdrop-blur-xl">
      <div className="flex items-center gap-2 text-sm">
        <Link to="/" className="text-ink-muted hover:text-white transition-colors">
          Home
        </Link>
        {pathname !== '/' && (
          <>
            <ChevronRight className="h-4 w-4 text-ink-faint" />
            <span className="font-medium text-transparent bg-clip-text bg-gradient-to-r from-white to-white/70">{title}</span>
          </>
        )}
      </div>
    </header>
  )
}
