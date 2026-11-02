import { NavLink, Outlet } from 'react-router-dom'
import { MessageSquareQuote, Search } from 'lucide-react'

const tabs = [
  { to: 'answers', label: 'Share of Model', icon: MessageSquareQuote },
  { to: 'questions', label: 'Questions', icon: Search },
]

export default function MeasureLayout() {
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-1 bg-surface-tertiary rounded-xl p-1 w-fit">
        {tabs.map(t => (
          <NavLink key={t.to} to={t.to} className={({ isActive }) =>
            `flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${isActive ? 'bg-white text-text-primary shadow-soft' : 'text-text-secondary hover:text-text-primary'}`}>
            <t.icon className="w-4 h-4" />{t.label}
          </NavLink>
        ))}
      </div>
      <Outlet />
    </div>
  )
}
