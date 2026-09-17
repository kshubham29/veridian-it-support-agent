"""Audit trail writer/reader. Every agent action produces an immutable event."""
from __future__ import annotations

from typing import List, Optional

from .store import store


def log(
    event: str,
    detail: Optional[str] = None,
    ticket_id: Optional[str] = None,
    session_id: Optional[str] = None,
    actor: str = "Agent",
) -> dict:
    return store.add_audit(
        event=event, detail=detail, ticket_id=ticket_id, session_id=session_id, actor=actor
    )


def attach_session_events_to_ticket(session_id: str, ticket_id: str) -> None:
    """Back-fill the reasoning events from this turn onto the created ticket."""
    for entry in store.audit:
        if entry.get("session_id") == session_id and entry.get("ticket_id") is None:
            entry["ticket_id"] = ticket_id
    store.persist()


def for_ticket(ticket_id: str) -> List[dict]:
    return sorted(store.audit_for_ticket(ticket_id), key=lambda e: e["id"])


def for_session(session_id: str) -> List[dict]:
    return sorted(store.audit_for_session(session_id), key=lambda e: e["id"])


def recent(limit: int = 12) -> List[dict]:
    # Ordered by insertion sequence, not wall-clock: seeded history carries
    # its original (in-story) timestamps and must not outrank live agent events.
    return sorted(store.audit, key=lambda e: e["id"], reverse=True)[:limit]
