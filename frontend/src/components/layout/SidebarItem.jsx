import { NavLink } from 'react-router-dom'

export default function SidebarItem({ to, icon: Icon, label }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all duration-300 ${
          isActive
            ? 'bg-brand/10 text-white shadow-[inset_2px_0_0_0_#6366f1]'
            : 'text-sidebar-text hover:bg-surface-muted hover:text-white'
        }`
      }
    >
      {({ isActive }) => (
        <>
          <Icon className={`h-5 w-5 shrink-0 transition-colors duration-300 ${isActive ? 'text-brand drop-shadow-[0_0_8px_rgba(99,102,241,0.8)]' : 'group-hover:text-brand/70'}`} />
          <span>{label}</span>
          {isActive && (
            <div className="absolute inset-0 rounded-xl bg-gradient-to-r from-brand/5 to-transparent pointer-events-none"></div>
          )}
        </>
      )}
    </NavLink>
  )
}
