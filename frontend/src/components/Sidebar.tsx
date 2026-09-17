import { useEffect, useState } from 'react'
import { NavLink } from 'react-router-dom'
import {
  BookOpen,
  Bot,
  LayoutDashboard,
  MessageSquareText,
  Settings as SettingsIcon,
  Ticket,
  Users,
} from 'lucide-react'
import { api } from '../services/api'

const links = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/chat', label: 'AI Support', icon: MessageSquareText },
  { to: '/tickets', label: 'Tickets', icon: Ticket },
  { to: '/requests', label: 'Employee Requests', icon: Users },
  { to: '/knowledge-base', label: 'Knowledge Base', icon: BookOpen },
]

export default function Sidebar() {
  const [mode, setMode] = useState<string>('…')

  useEffect(() => {
    api
      .health()
      .then((h) => setMode(h.mode))
      .catch(() => setMode('offline'))
  }, [])

  const itemClass = ({ isActive }: { isActive: boolean }) =>
    [
      'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition',
      isActive ? 'bg-brand-50 text-brand-700' : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900',
    ].join(' ')

  return (
    <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 flex-col border-r border-slate-200 bg-white md:flex">
      <div className="flex items-center gap-3 border-b border-slate-200 px-5 py-5">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-900 text-white">
          <Bot className="h-5 w-5" />
        </div>
        <div>
          <p className="text-sm font-bold tracking-wide text-brand-900">VERIDIAN</p>
          <p className="text-[11px] uppercase tracking-wider text-slate-500">IT Service Agent</p>
        </div>
      </div>

      <nav className="flex-1 space-y-1 px-3 py-4">
        {links.map(({ to, label, icon: Icon }) => (
          <NavLink key={to} to={to} className={itemClass}>
            <Icon className="h-4 w-4" />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-slate-200 px-3 py-4">
        <NavLink to="/settings" className={itemClass}>
          <SettingsIcon className="h-4 w-4" />
          Settings
        </NavLink>
        <div className="mt-3 rounded-lg bg-slate-50 px-3 py-2">
          <p className="text-[11px] uppercase tracking-wider text-slate-500">Agent mode</p>
          <p className="text-sm font-semibold text-slate-700">
            {mode === 'llm' ? 'LLM Mode' : mode === 'offline' ? 'Backend offline' : 'Demo Mode'}
          </p>
        </div>
      </div>
    </aside>
  )
}
