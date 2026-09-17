import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, CheckCircle2, ShieldAlert } from 'lucide-react'
import { PriorityBadge, StatusBadge } from '../components/Badges'
import SourceCard from '../components/SourceCard'
import { EmptyState, ErrorState, Loading, PageHeader } from '../components/States'
import { useToast } from '../hooks/useToast'
import { api, ApiError } from '../services/api'
import type { AuditEvent, KBArticle, Ticket } from '../types'

export default function TicketDetail() {
  const { ticketId = '' } = useParams()
  const { push } = useToast()
  const [ticket, setTicket] = useState<Ticket | null>(null)
  const [audit, setAudit] = useState<AuditEvent[]>([])
  const [sources, setSources] = useState<KBArticle[]>([])
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    setError(null)
    Promise.all([api.ticket(ticketId), api.audit(ticketId), api.knowledgeBase()])
      .then(([t, a, kb]) => {
        setTicket(t)
        setAudit(a)
        setSources(kb.filter((k) => t.source_ids.includes(k.id)))
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Failed to load ticket.'))
  }, [ticketId])

  useEffect(load, [load])

  async function act(kind: 'resolve' | 'escalate') {
    setBusy(true)
    try {
      const updated =
        kind === 'resolve' ? await api.resolveTicket(ticketId) : await api.escalateTicket(ticketId)
      setTicket(updated)
      setAudit(await api.audit(ticketId))
      push(`${updated.ticket_id} is now ${updated.status}.`, 'success')
    } catch (err) {
      push(err instanceof ApiError ? err.message : 'Action failed.', 'error')
    } finally {
      setBusy(false)
    }
  }

  if (error) return <div className="p-6"><ErrorState message={error} onRetry={load} /></div>
  if (!ticket) return <Loading label="Loading ticket…" />

  const fields: [string, string][] = [
    ['Ticket ID', ticket.ticket_id],
    ['Request ID', ticket.request_id ?? '—'],
    ['Employee', ticket.employee],
    ['Email', ticket.email ?? '—'],
    ['Category', ticket.category],
    ['Assigned Team', ticket.assigned_team],
    ['Created At', ticket.created_at.replace('T', ' ')],
    ['Updated At', ticket.updated_at.replace('T', ' ')],
  ]

  return (
    <div>
      <PageHeader
        title={`Ticket ${ticket.ticket_id}`}
        subtitle={ticket.issue_summary}
        actions={
          <div className="flex gap-2">
            <Link to="/tickets" className="btn-secondary">
              <ArrowLeft className="h-4 w-4" /> Back
            </Link>
            <button className="btn-secondary" disabled={busy} onClick={() => act('escalate')}>
              <ShieldAlert className="h-4 w-4" /> Escalate
            </button>
            <button className="btn-primary" disabled={busy} onClick={() => act('resolve')}>
              <CheckCircle2 className="h-4 w-4" /> Resolve
            </button>
          </div>
        }
      />

      <div className="grid grid-cols-1 gap-4 p-6 lg:grid-cols-3">
        <div className="card p-5 lg:col-span-2">
          <div className="mb-4 flex flex-wrap items-center gap-2">
            <StatusBadge status={ticket.status} />
            <PriorityBadge priority={ticket.priority} />
            <span className={`chip ${ticket.is_active ? 'bg-blue-50 text-blue-700' : 'bg-slate-100 text-slate-500'}`}>
              {ticket.is_active ? 'Active case' : 'Closed — history only'}
            </span>
            <span className="chip bg-slate-100 text-slate-500">origin: {ticket.origin}</span>
          </div>

          <dl className="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2">
            {fields.map(([label, value]) => (
              <div key={label}>
                <dt className="text-xs uppercase tracking-wide text-slate-500">{label}</dt>
                <dd className="text-sm text-slate-800">{value}</dd>
              </div>
            ))}
          </dl>

          <div className="mt-5">
            <p className="text-xs uppercase tracking-wide text-slate-500">Action Taken</p>
            <p className="mt-1 whitespace-pre-line text-sm text-slate-700">
              {ticket.action_taken ?? 'No action recorded yet.'}
            </p>
          </div>

          <SourceCard sources={sources} />
        </div>

        <div className="card">
          <div className="border-b border-slate-200 px-5 py-4">
            <h2 className="text-sm font-semibold text-slate-800">Audit Trail</h2>
            <p className="text-xs text-slate-500">Every agent and human action on this ticket</p>
          </div>
          {audit.length === 0 ? (
            <EmptyState title="No audit events yet" />
          ) : (
            <ol className="relative space-y-4 px-5 py-4">
              {audit.map((e) => (
                <li key={e.id} className="relative border-l border-slate-200 pl-4">
                  <span className="absolute -left-[5px] top-1.5 h-2.5 w-2.5 rounded-full bg-brand-500" />
                  <p className="font-mono text-[11px] text-slate-400">
                    {e.timestamp.replace('T', ' ').slice(5)}
                  </p>
                  <p className="text-sm font-medium text-slate-800">{e.event}</p>
                  {e.detail && <p className="text-xs text-slate-500">{e.detail}</p>}
                  <p className="text-[11px] text-slate-400">by {e.actor}</p>
                </li>
              ))}
            </ol>
          )}
        </div>
      </div>
    </div>
  )
}
