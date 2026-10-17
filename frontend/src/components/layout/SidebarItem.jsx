import { NavLink } from 'react-router-dom'

export default function SidebarItem({ to, icon: Icon, label }) {
  return (
    <NavLink
      to={to}
      aria-label={label}
      title={label}
      className={({ isActive }) =>
        `group relative flex items-center justify-center gap-3 rounded-xl px-2 py-2.5 text-sm font-medium transition-all duration-300 md:justify-start md:px-3 ${
          isActive
            ? 'bg-brand/10 text-ink shadow-[inset_2px_0_0_0_#6366f1]'
            : 'text-ink-muted hover:bg-surface-muted hover:text-ink'
        }`
      }
    >
      {({ isActive }) => (
        <>
          <Icon aria-hidden="true" className={`h-5 w-5 shrink-0 transition-colors duration-300 ${isActive ? 'text-brand drop-shadow-[0_0_8px_rgba(99,102,241,0.8)]' : 'group-hover:text-brand/70'}`} />
          <span className="hidden md:inline">{label}</span>
          {isActive && (
            <div className="absolute inset-0 rounded-xl bg-gradient-to-r from-brand/5 to-transparent pointer-events-none"></div>
          )}
        </>
      )}
    </NavLink>
  )
}
