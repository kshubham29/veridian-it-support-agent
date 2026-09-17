"""Ticket creation and lifecycle operations."""
from __future__ import annotations

from typing import List, Optional

from .store import now_iso, store

ACTIVE_STATUSES = {"New", "In Progress", "Escalated", "Pending Approval", "Pending Employee"}


def list_tickets(
    status: Optional[str] = None,
    category: Optional[str] = None,
    priority: Optional[str] = None,
    search: Optional[str] = None,
) -> List[dict]:
    items = list(store.tickets)
    if status:
        items = [t for t in items if t["status"].lower() == status.lower()]
    if category:
        items = [t for t in items if t["category"].lower() == category.lower()]
    if priority:
        items = [t for t in items if t["priority"].lower() == priority.lower()]
    if search:
        q = search.lower()
        items = [
            t
            for t in items
            if q in t["ticket_id"].lower()
            or q in t["employee"].lower()
            or q in t["issue_summary"].lower()
            or q in t["category"].lower()
        ]
    return sorted(items, key=lambda t: t["created_at"], reverse=True)


def create_ticket(
    employee: str,
    issue_summary: str,
    category: str,
    priority: str = "MEDIUM",
    status: str = "New",
    assigned_team: str = "IT Service Desk",
    source_ids: Optional[List[str]] = None,
    action_taken: Optional[str] = None,
    email: Optional[str] = None,
    request_id: Optional[str] = None,
    origin: str = "agent",
) -> dict:
    ticket_id = store.next_ticket_id()
    timestamp = now_iso()
    ticket = {
        "ticket_id": ticket_id,
        "request_id": request_id,
        "employee": employee or "Unknown Employee",
        "email": email,
        "category": category,
        "issue_summary": issue_summary,
        "priority": priority,
        "status": status,
        "is_active": status in ACTIVE_STATUSES,
        "assigned_team": assigned_team,
        "action_taken": action_taken,
        "source_ids": source_ids or [],
        "created_at": timestamp,
        "updated_at": timestamp,
        "origin": origin,
    }
    return store.add_ticket(ticket)


def set_status(ticket_id: str, status: str, note: Optional[str] = None) -> Optional[dict]:
    ticket = store.get_ticket(ticket_id)
    if not ticket:
        return None
    return store.update_ticket(
        ticket_id,
        status=status,
        is_active=status in ACTIVE_STATUSES,
        action_taken=note or ticket.get("action_taken"),
    )


def stats() -> dict:
    tickets = store.tickets
    open_tickets = [t for t in tickets if t.get("is_active")]
    return {
        "total_requests": len(store.requests),
        "open_tickets": len(open_tickets),
        "resolved_tickets": len([t for t in tickets if t["status"] == "Resolved"]),
        "escalated_tickets": len([t for t in tickets if t["status"] == "Escalated"]),
        "pending_approval": len([t for t in tickets if t["status"] == "Pending Approval"]),
        "security_incidents": len([t for t in tickets if t["category"] == "Security Incident"]),
    }
