import { NavLink } from 'react-router-dom'

export default function SidebarItem({ to, icon: Icon, label }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
          isActive
            ? 'border-l-2 border-brand bg-sidebar-active text-sidebar-text-active'
            : 'border-l-2 border-transparent text-sidebar-text hover:bg-sidebar-hover hover:text-sidebar-text-active'
        }`
      }
    >
      <Icon className="h-5 w-5 shrink-0" />
      <span>{label}</span>
    </NavLink>
  )
}
