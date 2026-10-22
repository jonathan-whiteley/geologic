import { NavLink, Outlet } from 'react-router-dom'
import { LayoutDashboard, ListChecks } from 'lucide-react'

// Prompt Bank also stays active on a prompt's detail page (/measure/prompts/:id).
const tabs = [
  { to: '/measure', label: 'Overview', icon: LayoutDashboard, end: true },
  { to: '/measure/prompts', label: 'Prompt Bank', icon: ListChecks, end: false },
]

export default function MeasureLayout() {
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-1 bg-surface-tertiary rounded-xl p-1 w-fit">
        {tabs.map(t => (
          <NavLink key={t.to} to={t.to} end={t.end} className={({ isActive }) => `sub-item ${isActive ? 'active' : ''}`}>
            <t.icon className="w-4 h-4" />{t.label}
          </NavLink>
        ))}
      </div>
      <Outlet />
    </div>
  )
}
