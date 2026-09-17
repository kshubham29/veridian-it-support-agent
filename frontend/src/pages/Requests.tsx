import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Bot, PlayCircle } from 'lucide-react'
import { ErrorState, Loading, PageHeader } from '../components/States'
import { useToast } from '../hooks/useToast'
import { api, ApiError } from '../services/api'
import type { EmployeeRequest } from '../types'

export default function Requests() {
  const navigate = useNavigate()
  const { push } = useToast()
  const [requests, setRequests] = useState<EmployeeRequest[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)

  const load = useCallback(() => {
    setError(null)
    api
      .requests()
      .then(setRequests)
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Failed to load requests.'))
  }, [])

  useEffect(load, [load])

  async function runAgent(req: EmployeeRequest) {
    setBusyId(req.id)
    try {
      const res = await api.processRequest(req.id)
      push(
        res.ticket
          ? `${req.id}: ${res.decision.action} → ticket ${res.ticket.ticket_id}`
          : `${req.id}: ${res.decision.action.replace('_', ' ')}`,
        res.decision.escalation_required ? 'info' : 'success',
      )
      load()
    } catch (err) {
      push(err instanceof ApiError ? err.message : 'Agent run failed.', 'error')
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div>
      <PageHeader
        title="Employee Requests"
        subtitle="Seeded inbox for the week of 21–25 Sep 2026 (REQ-01 to REQ-15)"
      />
      <div className="p-6">
        {error ? (
          <ErrorState message={error} onRetry={load} />
        ) : !requests ? (
          <Loading label="Loading requests…" />
        ) : (
          <div className="card overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200">
              <thead className="bg-slate-50">
                <tr>
                  <th className="th">Request ID</th>
                  <th className="th">Employee</th>
                  <th className="th">Date</th>
                  <th className="th">Request</th>
                  <th className="th">Initial Action</th>
                  <th className="th">Agent Status</th>
                  <th className="th">Open in AI Agent</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {requests.map((r) => (
                  <tr key={r.id} className="hover:bg-slate-50">
                    <td className="td font-medium text-brand-700">{r.id}</td>
                    <td className="td">
                      <p className="font-medium text-slate-800">{r.employee}</p>
                      <p className="text-xs text-slate-500">{r.email}</p>
                    </td>
                    <td className="td whitespace-nowrap">{r.date_opened}</td>
                    <td className="td max-w-sm">{r.request}</td>
                    <td className="td text-xs text-slate-500">{r.initial_action}</td>
                    <td className="td">
                      {r.ticket_id ? (
                        <button
                          className="chip bg-brand-50 text-brand-700"
                          onClick={() => navigate(`/tickets/${r.ticket_id}`)}
                        >
                          {r.agent_status}
                        </button>
                      ) : (
                        <span className="chip bg-slate-100 text-slate-600">{r.agent_status}</span>
                      )}
                    </td>
                    <td className="td">
                      <div className="flex gap-2">
                        <button
                          className="btn-secondary px-2 py-1 text-xs"
                          onClick={() =>
                            navigate(
                              `/chat?request=${r.id}&employee=${encodeURIComponent(r.employee)}` +
                                `&email=${encodeURIComponent(r.email)}&message=${encodeURIComponent(r.request)}`,
                            )
                          }
                        >
                          <Bot className="h-3.5 w-3.5" /> Chat
                        </button>
                        <button
                          className="btn-secondary px-2 py-1 text-xs"
                          disabled={busyId === r.id}
                          onClick={() => runAgent(r)}
                        >
                          <PlayCircle className="h-3.5 w-3.5" />
                          {busyId === r.id ? 'Running…' : 'Run agent'}
                        </button>
                      </div>
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
