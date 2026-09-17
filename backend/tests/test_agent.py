"""Acceptance tests covering the five demo scenarios and the API surface.

Run from backend/:  python -m pytest -q   (or: python tests/test_agent.py)
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)


def chat(message, session_id=None, **kw):
    body = {"message": message, "session_id": session_id, **kw}
    resp = client.post("/api/chat", json=body)
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_health_and_mode():
    data = client.get("/api/health").json()
    assert data["status"] == "ok"
    assert data["mode"] in {"mock", "llm"}


def test_seed_data_loaded():
    assert len(client.get("/api/requests").json()) == 15
    tickets = client.get("/api/tickets").json()
    assert len([t for t in tickets if t["origin"] == "seed"]) == 10
    assert len(client.get("/api/knowledge-base").json()) == 11
    closed = [t for t in tickets if t["ticket_id"] in {"TK-1042", "TK-1045", "TK-1050"}]
    assert all(not t["is_active"] for t in closed)


def test_demo_1_password_lockout():
    out = chat("I'm locked out of my account. I tried my password 6 times.")
    d = out["decision"]
    assert d["category"] == "Password"
    assert "KB-01" in d["source_ids"]
    assert d["ticket_required"] and out["ticket"]
    assert "unlock" in d["response"].lower()
    assert out["ticket"]["assigned_team"] == "IT Service Desk"
    assert any("Ticket" in e["event"] for e in out["audit"])


def test_demo_2_phishing():
    out = chat("I received an email asking for my login. Should I forward it to my teammates?")
    d = out["decision"]
    assert d["category"] == "Security Incident"
    assert d["priority"] == "HIGH"
    assert d["action"] == "ESCALATE"
    assert d["source_ids"] == ["KB-09"]
    assert "security@veridian-corp.example" in d["response"]
    assert "not forward" in d["response"].lower() or "do not forward" in d["response"].lower()
    assert out["ticket"]["assigned_team"] == "Security"
    assert out["ticket"]["status"] == "Escalated"


def test_demo_3_contractor_vpn():
    out = chat("My new contractor needs VPN access.")
    d = out["decision"]
    assert d["category"] == "VPN"
    assert "KB-02" in d["source_ids"]
    assert "manager approval" in d["response"].lower()
    assert "access request form" in d["response"].lower()
    assert out["ticket"]["status"] == "Pending Approval"


def test_demo_4_laptop_policy_conflict():
    out = chat("My laptop won't turn on and I've had it for 3.5 years.")
    d = out["decision"]
    assert d["category"] == "Laptop/Hardware"
    assert set(d["source_ids"]) == {"KB-03", "ASSET-01"}
    assert d["policy_conflict"]
    assert out["ticket"]["status"] == "Pending Approval"
    assert "Finance" in out["ticket"]["assigned_team"]


def test_demo_5_mailbox():
    out = chat("My mailbox is full and I can't send emails.")
    d = out["decision"]
    assert d["category"] == "Email/Mailbox"
    assert d["source_ids"] == ["KB-06"]
    assert d["action"] == "RESOLVE"
    assert "25gb" in d["response"].lower() and "50gb" in d["response"].lower()
    assert "archive" in d["response"].lower()
    assert out["ticket"] is None


def test_vague_request_asks_clarification():
    out = chat("hey can you help, its not working", session_id="s-vague")
    assert out["decision"]["action"] == "FOLLOW_UP"
    assert out["decision"]["needs_follow_up"]
    assert "laptop" in out["decision"]["follow_up_question"].lower()


def test_vpn_follow_up_then_resolve():
    s = "s-vpn"
    first = chat("My VPN isn't working.", session_id=s)
    assert first["decision"]["action"] == "FOLLOW_UP"
    assert "expired" in first["decision"]["follow_up_question"].lower()
    second = chat("Yes", session_id=s)
    d = second["decision"]
    assert d["category"] == "VPN" and d["action"] == "RESOLVE"
    assert "KB-02" in d["source_ids"] and "90 days" in d["response"]


def test_printer_follow_up_chain_creates_ticket():
    s = "s-printer"
    first = chat("Printer on the 3rd floor keeps showing paper jam even though there's no jam.", session_id=s)
    assert first["decision"]["action"] == "FOLLOW_UP"
    second = chat("Yes, I restarted the spooler already", session_id=s)
    assert second["decision"]["needs_follow_up"] and "asset tag" in second["decision"]["response"].lower()
    third = chat("PRN-3045", session_id=s)
    assert third["ticket"] is not None
    assert "PRN-3045" in third["ticket"]["issue_summary"]
    assert third["decision"]["source_ids"] == ["KB-05"]


def test_guest_wifi_no_ticket():
    out = chat("Can I get Wi-Fi access for a guest visiting our office tomorrow?")
    assert out["decision"]["action"] == "RESOLVE"
    assert out["decision"]["source_ids"] == ["KB-07"]
    assert out["ticket"] is None


def test_admin_access_has_no_invented_policy():
    out = chat("Can someone give me admin access to the finance reporting server? Need it urgently for month-end.")
    d = out["decision"]
    assert d["category"] == "Access Request"
    assert d["action"] == "ESCALATE"
    assert d["source_ids"] == []
    assert "no policy" in d["response"].lower()
    assert "TK-1050" in d["precedent_ticket_ids"]


def test_wfh_equipment():
    out = chat("I've started working from home 4 days a week, how do I get a monitor?")
    d = out["decision"]
    assert d["category"] == "WFH Equipment"
    assert d["source_ids"] == ["KB-10"]
    assert out["ticket"]["status"] == "Pending Approval"


def test_non_catalog_software():
    out = chat("Need approval to install a data-analysis tool that's not in the software catalog.")
    d = out["decision"]
    assert d["category"] == "Software" and d["source_ids"] == ["KB-04"]
    assert out["ticket"]["assigned_team"] == "IT Security"
    assert "3-5 business days" in d["response"]


def test_expense_tool_follow_up():
    s = "s-exp"
    first = chat("I can't log into the expense tool, keeps saying invalid credentials.", session_id=s)
    assert first["decision"]["category"] == "Finance/Expense"
    assert first["decision"]["action"] == "FOLLOW_UP"
    second = chat("Yes I already have an account", session_id=s)
    assert second["ticket"]["assigned_team"] == "IT Service Desk"


def test_empty_message_rejected():
    assert client.post("/api/chat", json={"message": "   "}).status_code == 422


def test_ticket_audit_and_lifecycle():
    out = chat("I'm locked out of my account after 6 failed attempts.")
    ticket_id = out["ticket"]["ticket_id"]
    audit = client.get(f"/api/audit/{ticket_id}").json()
    assert len(audit) >= 4
    assert any("Classified" in e["event"] for e in audit)
    resolved = client.post(f"/api/tickets/{ticket_id}/resolve").json()
    assert resolved["status"] == "Resolved" and resolved["is_active"] is False
    escalated = client.post(f"/api/tickets/{ticket_id}/escalate?team=Security").json()
    assert escalated["status"] == "Escalated" and escalated["assigned_team"] == "Security"
    assert client.get("/api/tickets/TK-9999").status_code == 404


def test_process_seeded_request_updates_status():
    out = client.post("/api/requests/REQ-08/process").json()
    assert out["decision"]["category"] == "Security Incident"
    req = next(r for r in client.get("/api/requests").json() if r["id"] == "REQ-08")
    assert req["ticket_id"] == out["ticket"]["ticket_id"]


def test_dashboard_stats():
    stats = client.get("/api/dashboard/stats").json()
    assert stats["total_requests"] == 15
    assert stats["open_tickets"] >= 5
    assert stats["security_incidents"] >= 1
    assert len(stats["recent_activity"]) > 0


def test_kb_search():
    assert len(client.get("/api/knowledge-base?q=vpn").json()) >= 1
    assert client.get("/api/knowledge-base/KB-09").json()["title"] == "Security Incident Reporting"
    assert client.get("/api/knowledge-base/KB-99").status_code == 404


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([os.path.abspath(__file__), "-q"]))
