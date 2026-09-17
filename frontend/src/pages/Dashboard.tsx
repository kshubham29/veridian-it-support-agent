import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Activity,
  CheckCircle2,
  ClipboardList,
  Clock3,
  ShieldAlert,
  Ticket as TicketIcon,
  AlertTriangle,
} from 'lucide-react'
import { ModeBadge } from '../components/Badges'
import { ErrorState, Loading, PageHeader } from '../components/States'
import { api, ApiError } from '../services/api'
import type { DashboardStats } from '../types'

const cards = [
  { key: 'total_requests', label: 'Total Requests', icon: ClipboardList, tone: 'text-slate-600' },
  { key: 'open_tickets', label: 'Open Tickets', icon: TicketIcon, tone: 'text-blue-600' },
  { key: 'resolved_tickets', label: 'Resolved', icon: CheckCircle2, tone: 'text-emerald-600' },
  { key: 'escalated_tickets', label: 'Escalated', icon: AlertTriangle, tone: 'text-rose-600' },
  { key: 'pending_approval', label: 'Pending Approval', icon: Clock3, tone: 'text-amber-600' },
  { key: 'security_incidents', label: 'Security Incidents', icon: ShieldAlert, tone: 'text-rose-700' },
] as const

export default function Dashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    setError(null)
    api
      .stats()
      .then(setStats)
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Failed to load dashboard.'))
  }, [])

  useEffect(load, [load])

  return (
    <div>
      <PageHeader
        title="Dashboard"
        subtitle="Live view of employee requests, agent decisions and ticket flow"
        actions={stats && <ModeBadge mode={stats.mode} />}
      />
      <div className="p-6">
        {error ? (
          <ErrorState message={error} onRetry={load} />
        ) : !stats ? (
          <Loading label="Loading dashboard…" />
        ) : (
          <>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {cards.map(({ key, label, icon: Icon, tone }) => (
                <div key={key} className="card p-5">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium text-slate-500">{label}</p>
                    <Icon className={`h-5 w-5 ${tone}`} />
                  </div>
                  <p className="mt-3 text-3xl font-semibold text-slate-900">{stats[key]}</p>
                </div>
              ))}
            </div>

            <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-3">
              <div className="card lg:col-span-2">
                <div className="flex items-center gap-2 border-b border-slate-200 px-5 py-4">
                  <Activity className="h-4 w-4 text-brand-600" />
                  <h2 className="text-sm font-semibold text-slate-800">Recent Activity</h2>
                </div>
                <ul className="divide-y divide-slate-100">
                  {stats.recent_activity.map((a, i) => (
                    <li key={i} className="flex items-start gap-3 px-5 py-3">
                      <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-brand-500" />
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium text-slate-800">
                          {a.ticket_id ? `${a.ticket_id} → ` : ''}
                          {a.event}
                        </p>
                        {a.detail && <p className="truncate text-xs text-slate-500">{a.detail}</p>}
                      </div>
                      <span className="whitespace-nowrap text-xs text-slate-400">
                        {a.timestamp.replace('T', ' ').slice(5, 16)}
                      </span>
                    </li>
                  ))}
                  {stats.recent_activity.length === 0 && (
                    <li className="px-5 py-6 text-sm text-slate-500">No agent activity yet.</li>
                  )}
                </ul>
              </div>

              <div className="card p-5">
                <h2 className="text-sm font-semibold text-slate-800">Quick start</h2>
                <p className="mt-1 text-xs text-slate-500">
                  Run a demo scenario through the agent, or triage the seeded employee requests.
                </p>
                <div className="mt-4 space-y-2">
                  <Link className="btn-primary w-full" to="/chat">
                    Open AI Support
                  </Link>
                  <Link className="btn-secondary w-full" to="/requests">
                    Employee Requests
                  </Link>
                  <Link className="btn-secondary w-full" to="/tickets">
                    Ticket Queue
                  </Link>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
