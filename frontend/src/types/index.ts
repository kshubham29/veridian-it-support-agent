export type Priority = 'LOW' | 'MEDIUM' | 'HIGH'
export type AgentAction = 'RESOLVE' | 'FOLLOW_UP' | 'CREATE_TICKET' | 'ESCALATE'
export type TicketStatus =
  | 'New'
  | 'In Progress'
  | 'Resolved'
  | 'Escalated'
  | 'Pending Approval'
  | 'Pending Employee'
  | 'Rejected'

export interface KBArticle {
  id: string
  title: string
  category: string
  text: string
  keywords: string[]
  issued_by?: string | null
  last_updated?: string | null
}

export interface EmployeeRequest {
  id: string
  employee: string
  email: string
  date_opened: string
  request: string
  initial_action: string
  agent_status: string
  ticket_id?: string | null
}

export interface Ticket {
  ticket_id: string
  request_id?: string | null
  employee: string
  email?: string | null
  category: string
  issue_summary: string
  priority: Priority
  status: TicketStatus
  is_active: boolean
  assigned_team: string
  action_taken?: string | null
  source_ids: string[]
  created_at: string
  updated_at: string
  origin: string
}

export interface AuditEvent {
  id: string
  ticket_id?: string | null
  session_id?: string | null
  timestamp: string
  actor: string
  event: string
  detail?: string | null
}

export interface AgentDecision {
  category: string
  intent: string
  response: string
  action: AgentAction
  priority: Priority
  source_ids: string[]
  needs_follow_up: boolean
  follow_up_question?: string | null
  ticket_required: boolean
  escalation_required: boolean
  assigned_team: string
  confidence: number
  policy_conflict?: string | null
  precedent_ticket_ids: string[]
}

export interface ChatResponse {
  session_id: string
  decision: AgentDecision
  sources: KBArticle[]
  ticket?: Ticket | null
  audit: AuditEvent[]
  mode: string
}

export interface DashboardStats {
  total_requests: number
  open_tickets: number
  resolved_tickets: number
  escalated_tickets: number
  pending_approval: number
  security_incidents: number
  recent_activity: {
    timestamp: string
    actor: string
    event: string
    detail?: string | null
    ticket_id?: string | null
  }[]
  mode: string
}

export interface ChatMessage {
  id: string
  role: 'user' | 'agent'
  text: string
  decision?: AgentDecision
  sources?: KBArticle[]
  ticket?: Ticket | null
  timestamp: string
}
