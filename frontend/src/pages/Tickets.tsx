import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search } from 'lucide-react'
import { PriorityBadge, StatusBadge } from '../components/Badges'
import { EmptyState, ErrorState, Loading, PageHeader } from '../components/States'
import { api, ApiError } from '../services/api'
import type { Ticket } from '../types'

const STATUSES = ['All', 'New', 'In Progress', 'Resolved', 'Escalated', 'Pending Approval', 'Pending Employee', 'Rejected']
const CATEGORIES = [
  'All',
  'Password',
  'VPN',
  'Laptop/Hardware',
  'Software',
  'Printer',
  'Email/Mailbox',
  'Guest Wi-Fi',
  'Security Incident',
  'Finance/Expense',
  'Access Request',
  'WFH Equipment',
]
const PRIORITIES = ['All', 'LOW', 'MEDIUM', 'HIGH']

export default function Tickets() {
  const navigate = useNavigate()
  const [tickets, setTickets] = useState<Ticket[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [status, setStatus] = useState('All')
  const [category, setCategory] = useState('All')
  const [priority, setPriority] = useState('All')
  const [search, setSearch] = useState('')

  const load = useCallback(() => {
    setError(null)
    setTickets(null)
    api
      .tickets({ status, category, priority, search })
      .then(setTickets)
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Failed to load tickets.'))
  }, [status, category, priority, search])

  useEffect(() => {
    const t = setTimeout(load, 150)
    return () => clearTimeout(t)
  }, [load])

  return (
    <div>
      <PageHeader title="Ticket Queue" subtitle="Agent-created tickets plus existing ticket history" />
      <div className="p-6">
        <div className="card mb-4 flex flex-wrap items-center gap-3 p-4">
          <div className="relative flex-1 min-w-[220px]">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
            <input
              className="input pl-9"
              placeholder="Search ticket ID, employee or issue…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <select className="input w-44" value={status} onChange={(e) => setStatus(e.target.value)}>
            {STATUSES.map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
          <select className="input w-44" value={category} onChange={(e) => setCategory(e.target.value)}>
            {CATEGORIES.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
          <select className="input w-32" value={priority} onChange={(e) => setPriority(e.target.value)}>
            {PRIORITIES.map((p) => (
              <option key={p}>{p}</option>
            ))}
          </select>
        </div>

        {error ? (
          <ErrorState message={error} onRetry={load} />
        ) : !tickets ? (
          <Loading label="Loading tickets…" />
        ) : tickets.length === 0 ? (
          <div className="card">
            <EmptyState title="No tickets match these filters" hint="Try clearing the search or filters." />
          </div>
        ) : (
          <div className="card overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200">
              <thead className="bg-slate-50">
                <tr>
                  <th className="th">Ticket ID</th>
                  <th className="th">Employee</th>
                  <th className="th">Category</th>
                  <th className="th">Issue</th>
                  <th className="th">Priority</th>
                  <th className="th">Status</th>
                  <th className="th">Assigned Team</th>
                  <th className="th">Source</th>
                  <th className="th">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {tickets.map((t) => (
                  <tr
                    key={t.ticket_id}
                    className="cursor-pointer hover:bg-slate-50"
                    onClick={() => navigate(`/tickets/${t.ticket_id}`)}
                  >
                    <td className="td font-medium text-brand-700">{t.ticket_id}</td>
                    <td className="td">{t.employee}</td>
                    <td className="td">{t.category}</td>
                    <td className="td max-w-xs">{t.issue_summary}</td>
                    <td className="td">
                      <PriorityBadge priority={t.priority} />
                    </td>
                    <td className="td">
                      <StatusBadge status={t.status} />
                    </td>
                    <td className="td">{t.assigned_team}</td>
                    <td className="td text-xs text-slate-500">
                      {t.source_ids.length ? t.source_ids.join(', ') : '—'}
                    </td>
                    <td className="td">
                      <button
                        className="btn-secondary px-2 py-1 text-xs"
                        onClick={(e) => {
                          e.stopPropagation()
                          navigate(`/tickets/${t.ticket_id}`)
                        }}
                      >
                        View
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
