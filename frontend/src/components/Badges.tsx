import type { Priority, TicketStatus } from '../types'

const statusStyles: Record<string, string> = {
  New: 'bg-slate-100 text-slate-700',
  'In Progress': 'bg-blue-50 text-blue-700',
  Resolved: 'bg-emerald-50 text-emerald-700',
  Escalated: 'bg-rose-50 text-rose-700',
  'Pending Approval': 'bg-amber-50 text-amber-700',
  'Pending Employee': 'bg-violet-50 text-violet-700',
  Rejected: 'bg-slate-200 text-slate-600',
}

const priorityStyles: Record<string, string> = {
  LOW: 'bg-slate-100 text-slate-600',
  MEDIUM: 'bg-amber-50 text-amber-700',
  HIGH: 'bg-rose-50 text-rose-700',
}

const actionStyles: Record<string, string> = {
  RESOLVE: 'bg-emerald-50 text-emerald-700',
  CREATE_TICKET: 'bg-blue-50 text-blue-700',
  ESCALATE: 'bg-rose-50 text-rose-700',
  FOLLOW_UP: 'bg-violet-50 text-violet-700',
}

export function StatusBadge({ status }: { status: TicketStatus | string }) {
  return <span className={`chip ${statusStyles[status] ?? 'bg-slate-100 text-slate-700'}`}>{status}</span>
}

export function PriorityBadge({ priority }: { priority: Priority | string }) {
  return <span className={`chip ${priorityStyles[priority] ?? 'bg-slate-100 text-slate-600'}`}>{priority}</span>
}

export function ActionBadge({ action }: { action: string }) {
  return (
    <span className={`chip ${actionStyles[action] ?? 'bg-slate-100 text-slate-700'}`}>
      {action.replace('_', ' ')}
    </span>
  )
}

export function ModeBadge({ mode }: { mode: string }) {
  const isLlm = mode === 'llm'
  return (
    <span className={`chip ${isLlm ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'}`}>
      {isLlm ? 'LLM Mode' : mode === 'mock-fallback' ? 'Demo Mode (LLM fallback)' : 'Demo Mode'}
    </span>
  )
}
