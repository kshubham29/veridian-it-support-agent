import type {
  AuditEvent,
  ChatResponse,
  DashboardStats,
  EmployeeRequest,
  KBArticle,
  Ticket,
} from '../types'

const BASE = import.meta.env.VITE_API_BASE ?? ''

export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${BASE}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...init,
    })
  } catch {
    throw new ApiError('Cannot reach the API. Is the backend running on port 8000?', 0)
  }
  if (!res.ok) {
    let detail = `Request failed (${res.status})`
    try {
      const body = await res.json()
      if (body?.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch {
      /* keep default message */
    }
    throw new ApiError(detail, res.status)
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

export const api = {
  health: () => request<{ status: string; mode: string; model: string | null }>('/api/health'),
  chat: (payload: {
    message: string
    session_id?: string | null
    employee?: string | null
    email?: string | null
    request_id?: string | null
  }) => request<ChatResponse>('/api/chat', { method: 'POST', body: JSON.stringify(payload) }),
  tickets: (params: Record<string, string> = {}) => {
    const qs = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v && v !== 'All') as [string, string][],
    ).toString()
    return request<Ticket[]>(`/api/tickets${qs ? `?${qs}` : ''}`)
  },
  ticket: (id: string) => request<Ticket>(`/api/tickets/${id}`),
  createTicket: (payload: Record<string, unknown>) =>
    request<Ticket>('/api/tickets', { method: 'POST', body: JSON.stringify(payload) }),
  resolveTicket: (id: string) => request<Ticket>(`/api/tickets/${id}/resolve`, { method: 'POST' }),
  escalateTicket: (id: string, team = 'Security') =>
    request<Ticket>(`/api/tickets/${id}/escalate?team=${encodeURIComponent(team)}`, { method: 'POST' }),
  audit: (ticketId: string) => request<AuditEvent[]>(`/api/audit/${ticketId}`),
  requests: () => request<EmployeeRequest[]>('/api/requests'),
  processRequest: (id: string) =>
    request<ChatResponse>(`/api/requests/${id}/process`, { method: 'POST' }),
  knowledgeBase: (q = '') =>
    request<KBArticle[]>(`/api/knowledge-base${q ? `?q=${encodeURIComponent(q)}` : ''}`),
  stats: () => request<DashboardStats>('/api/dashboard/stats'),
  reset: () => request<{ status: string }>('/api/reset', { method: 'POST' }),
}
