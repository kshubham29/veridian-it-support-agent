"""All HTTP endpoints for the Veridian IT Service Agent."""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from ..schemas.models import (
    AuditEvent,
    ChatRequest,
    ChatResponse,
    DashboardStats,
    EmployeeRequest,
    KBArticle,
    Ticket,
    TicketCreate,
)
from ..services import agent, audit_service, llm, retrieval, ticket_service
from ..services.store import store

router = APIRouter(prefix="/api")


# ------------------------------------------------------------------ system
@router.get("/health")
def health():
    return {"status": "ok", "mode": llm.mode(), "model": llm.config.model if llm.config.enabled else None}


@router.post("/reset")
def reset():
    """Reset all runtime state back to the seed data (handy mid-demo)."""
    store.reset()
    return {"status": "reset", "tickets": len(store.tickets), "requests": len(store.requests)}


# -------------------------------------------------------------------- chat
@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest):
    if not payload.message or not payload.message.strip():
        raise HTTPException(status_code=422, detail="Message cannot be empty.")
    try:
        result = agent.handle_message(
            message=payload.message.strip(),
            session_id=payload.session_id,
            employee=payload.employee,
            email=payload.email,
            request_id=payload.request_id,
            auto_create_ticket=payload.auto_create_ticket,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=f"Agent failure: {exc}") from exc
    return result


# ----------------------------------------------------------------- tickets
@router.get("/tickets", response_model=List[Ticket])
def get_tickets(
    status: Optional[str] = None,
    category: Optional[str] = None,
    priority: Optional[str] = None,
    search: Optional[str] = None,
):
    return ticket_service.list_tickets(status, category, priority, search)


@router.post("/tickets", response_model=Ticket, status_code=201)
def post_ticket(payload: TicketCreate):
    if not payload.issue_summary.strip():
        raise HTTPException(status_code=422, detail="issue_summary is required.")
    ticket = ticket_service.create_ticket(
        employee=payload.employee,
        email=payload.email,
        category=payload.category,
        issue_summary=payload.issue_summary,
        priority=payload.priority,
        status=payload.status,
        assigned_team=payload.assigned_team,
        source_ids=payload.source_ids,
        action_taken=payload.action_taken,
        request_id=payload.request_id,
        origin="manual",
    )
    audit_service.log(
        f"Ticket {ticket['ticket_id']} created manually",
        detail=f"Status: {ticket['status']} | Team: {ticket['assigned_team']}",
        ticket_id=ticket["ticket_id"],
        actor="User",
    )
    return ticket


@router.get("/tickets/{ticket_id}", response_model=Ticket)
def get_ticket(ticket_id: str):
    ticket = store.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found.")
    return ticket


@router.post("/tickets/{ticket_id}/resolve", response_model=Ticket)
def resolve_ticket(ticket_id: str, note: Optional[str] = None):
    ticket = ticket_service.set_status(ticket_id, "Resolved", note or "Resolved by IT agent.")
    if not ticket:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found.")
    audit_service.log(
        "Ticket resolved", detail=note or "Marked resolved", ticket_id=ticket_id, actor="User"
    )
    return ticket


@router.post("/tickets/{ticket_id}/escalate", response_model=Ticket)
def escalate_ticket(ticket_id: str, team: str = "Security", note: Optional[str] = None):
    ticket = store.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found.")
    ticket = ticket_service.set_status(ticket_id, "Escalated", note or f"Escalated to {team}.")
    store.update_ticket(ticket_id, assigned_team=team, priority="HIGH")
    audit_service.log(
        f"Escalated to {team}", detail=note or "Manual escalation", ticket_id=ticket_id, actor="User"
    )
    return store.get_ticket(ticket_id)


# ------------------------------------------------------------------ audit
@router.get("/audit/{ticket_id}", response_model=List[AuditEvent])
def get_audit(ticket_id: str):
    if not store.get_ticket(ticket_id):
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found.")
    return audit_service.for_ticket(ticket_id)


@router.get("/audit", response_model=List[AuditEvent])
def get_recent_audit(limit: int = Query(15, ge=1, le=100)):
    return audit_service.recent(limit)


# --------------------------------------------------------------- requests
@router.get("/requests", response_model=List[EmployeeRequest])
def get_requests():
    return store.requests


@router.post("/requests/{request_id}/process", response_model=ChatResponse)
def process_request(request_id: str):
    try:
        return agent.process_request(request_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Request {request_id} not found.")


# --------------------------------------------------------- knowledge base
@router.get("/knowledge-base", response_model=List[KBArticle])
def get_kb(q: Optional[str] = None):
    return retrieval.keyword_filter(q or "")


@router.get("/knowledge-base/{kb_id}", response_model=KBArticle)
def get_kb_article(kb_id: str):
    article = store.kb_by_id(kb_id)
    if not article:
        raise HTTPException(status_code=404, detail=f"Policy {kb_id} not found.")
    return article


# -------------------------------------------------------------- dashboard
@router.get("/dashboard/stats", response_model=DashboardStats)
def dashboard_stats():
    data = ticket_service.stats()
    data["recent_activity"] = [
        {
            "timestamp": e["timestamp"],
            "actor": e["actor"],
            "event": e["event"],
            "detail": e["detail"],
            "ticket_id": e.get("ticket_id"),
        }
        for e in audit_service.recent(8)
    ]
    data["mode"] = llm.mode()
    return data
