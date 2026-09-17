"""Pydantic schemas shared across the API and the agent layer."""
from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

Category = Literal[
    "Password",
    "VPN",
    "Laptop/Hardware",
    "Software",
    "Printer",
    "Email/Mailbox",
    "Guest Wi-Fi",
    "Security Incident",
    "Finance/Expense",
    "Access Request",
    "WFH Equipment",
    "Unknown",
]

Action = Literal["RESOLVE", "FOLLOW_UP", "CREATE_TICKET", "ESCALATE"]
Priority = Literal["LOW", "MEDIUM", "HIGH"]
Status = Literal[
    "New",
    "In Progress",
    "Resolved",
    "Escalated",
    "Pending Approval",
    "Pending Employee",
    "Rejected",
]


class KBArticle(BaseModel):
    id: str
    title: str
    category: str
    text: str
    keywords: List[str] = []
    issued_by: Optional[str] = None
    last_updated: Optional[str] = None


class EmployeeRequest(BaseModel):
    id: str
    employee: str
    email: str
    date_opened: str
    request: str
    initial_action: str
    agent_status: str = "Not processed"
    ticket_id: Optional[str] = None


class AuditEvent(BaseModel):
    id: str
    ticket_id: Optional[str] = None
    session_id: Optional[str] = None
    timestamp: str
    actor: str = "Agent"
    event: str
    detail: Optional[str] = None


class Ticket(BaseModel):
    ticket_id: str
    request_id: Optional[str] = None
    employee: str
    email: Optional[str] = None
    category: str
    issue_summary: str
    priority: Priority = "MEDIUM"
    status: Status = "New"
    is_active: bool = True
    assigned_team: str = "IT Service Desk"
    action_taken: Optional[str] = None
    source_ids: List[str] = []
    created_at: str
    updated_at: str
    origin: str = "agent"


class TicketCreate(BaseModel):
    employee: str = Field(default="Demo Employee")
    email: Optional[str] = None
    category: str = "Unknown"
    issue_summary: str
    priority: Priority = "MEDIUM"
    status: Status = "New"
    assigned_team: str = "IT Service Desk"
    action_taken: Optional[str] = None
    source_ids: List[str] = []
    request_id: Optional[str] = None


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    employee: Optional[str] = None
    email: Optional[str] = None
    request_id: Optional[str] = None
    auto_create_ticket: bool = True


class AgentDecision(BaseModel):
    """The structured contract returned by the agent layer (mock or LLM)."""

    category: Category = "Unknown"
    intent: str = "unclassified"
    response: str
    action: Action = "FOLLOW_UP"
    priority: Priority = "MEDIUM"
    source_ids: List[str] = []
    needs_follow_up: bool = False
    follow_up_question: Optional[str] = None
    ticket_required: bool = False
    escalation_required: bool = False
    assigned_team: str = "IT Service Desk"
    confidence: float = 0.5
    policy_conflict: Optional[str] = None
    precedent_ticket_ids: List[str] = []


class ChatResponse(BaseModel):
    session_id: str
    decision: AgentDecision
    sources: List[KBArticle] = []
    ticket: Optional[Ticket] = None
    audit: List[AuditEvent] = []
    mode: str = "mock"


class DashboardStats(BaseModel):
    total_requests: int
    open_tickets: int
    resolved_tickets: int
    escalated_tickets: int
    pending_approval: int
    security_incidents: int
    recent_activity: List[dict] = []
    mode: str = "mock"
