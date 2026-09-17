"""In-memory data store backed by JSON seed files.

Seed files under /data are treated as read-only. Anything the agent creates at
runtime (tickets, audit events, request status) is kept in memory and mirrored
to data/runtime_state.json so a demo survives a backend restart.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = BASE_DIR / "data"
RUNTIME_FILE = DATA_DIR / "runtime_state.json"


def _read(name: str) -> list:
    with open(DATA_DIR / name, "r", encoding="utf-8") as fh:
        return json.load(fh)


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


class Store:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.reset(persist=False)

    # ------------------------------------------------------------------ load
    def reset(self, persist: bool = True) -> None:
        with self._lock:
            self.knowledge_base: List[dict] = _read("knowledge_base.json")
            self.requests: List[dict] = [
                {**r, "agent_status": "Not processed", "ticket_id": None}
                for r in _read("employee_requests.json")
            ]
            self.tickets: List[dict] = _read("tickets.json")
            self.audit: List[dict] = []
            self._ticket_seq = 0
            self._audit_seq = 0
            self.sessions: Dict[str, dict] = {}
        self._seed_history_audit()
        if persist:
            self.persist()

    def _seed_history_audit(self) -> None:
        """Give seeded tickets a minimal audit trail so the UI is never empty."""
        for ticket in self.tickets:
            self.add_audit(
                ticket_id=ticket["ticket_id"],
                event="Ticket imported from legacy ticketing system",
                detail=f"Status: {ticket['status']} | Team: {ticket['assigned_team']}",
                actor="System",
                timestamp=ticket["created_at"],
            )
            if ticket.get("action_taken"):
                self.add_audit(
                    ticket_id=ticket["ticket_id"],
                    event="Last human update recorded",
                    detail=ticket["action_taken"],
                    actor="IT Agent (human)",
                    timestamp=ticket["updated_at"],
                )

    # --------------------------------------------------------------- persist
    def persist(self) -> None:
        try:
            payload = {
                "tickets": self.tickets,
                "audit": self.audit,
                "requests": self.requests,
                "saved_at": now_iso(),
            }
            with open(RUNTIME_FILE, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2)
        except OSError:
            # Persistence is a convenience, never fatal for the demo.
            pass

    def load_runtime(self) -> None:
        if not RUNTIME_FILE.exists():
            return
        try:
            with open(RUNTIME_FILE, "r", encoding="utf-8") as fh:
                payload = json.load(fh)
        except (OSError, json.JSONDecodeError):
            return
        with self._lock:
            self.tickets = payload.get("tickets", self.tickets)
            self.audit = payload.get("audit", self.audit)
            self.requests = payload.get("requests", self.requests)
            agent_ids = [
                t["ticket_id"] for t in self.tickets if t.get("origin") == "agent"
            ]
            self._ticket_seq = len(agent_ids)
            self._audit_seq = len(self.audit)

    # ------------------------------------------------------------------- kb
    def kb_by_id(self, kb_id: str) -> Optional[dict]:
        return next((a for a in self.knowledge_base if a["id"] == kb_id), None)

    def kb_many(self, ids: List[str]) -> List[dict]:
        return [a for kb_id in ids if (a := self.kb_by_id(kb_id))]

    # --------------------------------------------------------------- tickets
    def next_ticket_id(self) -> str:
        with self._lock:
            self._ticket_seq += 1
            return f"TK-AUTO-{self._ticket_seq:03d}"

    def add_ticket(self, ticket: dict) -> dict:
        with self._lock:
            self.tickets.append(ticket)
        self.persist()
        return ticket

    def get_ticket(self, ticket_id: str) -> Optional[dict]:
        return next((t for t in self.tickets if t["ticket_id"] == ticket_id), None)

    def update_ticket(self, ticket_id: str, **fields) -> Optional[dict]:
        ticket = self.get_ticket(ticket_id)
        if not ticket:
            return None
        ticket.update(fields)
        ticket["updated_at"] = now_iso()
        self.persist()
        return ticket

    # ----------------------------------------------------------------- audit
    def add_audit(
        self,
        event: str,
        ticket_id: Optional[str] = None,
        session_id: Optional[str] = None,
        detail: Optional[str] = None,
        actor: str = "Agent",
        timestamp: Optional[str] = None,
    ) -> dict:
        self._audit_seq += 1
        entry = {
            "id": f"AUD-{self._audit_seq:05d}",
            "ticket_id": ticket_id,
            "session_id": session_id,
            "timestamp": timestamp or now_iso(),
            "actor": actor,
            "event": event,
            "detail": detail,
        }
        self.audit.append(entry)
        return entry

    def audit_for_ticket(self, ticket_id: str) -> List[dict]:
        return [a for a in self.audit if a.get("ticket_id") == ticket_id]

    def audit_for_session(self, session_id: str) -> List[dict]:
        return [a for a in self.audit if a.get("session_id") == session_id]

    # -------------------------------------------------------------- requests
    def get_request(self, request_id: str) -> Optional[dict]:
        return next((r for r in self.requests if r["id"] == request_id), None)

    def update_request(self, request_id: str, **fields) -> Optional[dict]:
        req = self.get_request(request_id)
        if not req:
            return None
        req.update(fields)
        self.persist()
        return req

    # -------------------------------------------------------------- sessions
    def get_session(self, session_id: str) -> dict:
        return self.sessions.setdefault(
            session_id,
            {"slots": {}, "history": [], "pending_slot": None, "category": None},
        )


store = Store()
