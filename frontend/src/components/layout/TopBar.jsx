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
    <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b border-surface-border bg-white/80 px-8 backdrop-blur">
      <div className="flex items-center gap-2 text-sm">
        <Link to="/" className="text-ink-muted hover:text-ink transition-colors">
          Home
        </Link>
        {pathname !== '/' && (
          <>
            <ChevronRight className="h-4 w-4 text-ink-faint" />
            <span className="font-medium text-ink">{title}</span>
          </>
        )}
      </div>
    </header>
  )
}
