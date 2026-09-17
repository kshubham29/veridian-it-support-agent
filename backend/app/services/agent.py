"""Agent orchestrator.

Pipeline (identical in Demo mode and LLM mode):
    receive -> classify -> retrieve policy -> build context -> decide
    -> validate against guardrails -> act (ticket / escalate / resolve)
    -> write audit events -> return structured response
"""
from __future__ import annotations

import re
import uuid
from typing import Dict, List, Optional

from . import audit_service, llm, retrieval, rules, ticket_service
from .store import store

SECURITY_PATTERN = re.compile(
    r"phish|malware|ransomware|\bvirus\b|unauthori[sz]ed access|suspicious (email|login|link|activity)"
    r"|(email|mail|message).{0,40}(asking|asks|requesting).{0,20}(login|password|credential)",
    re.IGNORECASE,
)

VALID_ACTIONS = {"RESOLVE", "FOLLOW_UP", "CREATE_TICKET", "ESCALATE"}
VALID_PRIORITIES = {"LOW", "MEDIUM", "HIGH"}

STATUS_FOR_ACTION = {
    "ESCALATE": "Escalated",
    "CREATE_TICKET": "New",
    "RESOLVE": "Resolved",
    "FOLLOW_UP": "Pending Employee",
}


def _conversation_text(session: Dict, message: str) -> str:
    prior = " ".join(m["content"] for m in session["history"] if m["role"] == "user")
    return f"{prior} {message}".strip()


def _validate_llm_decision(raw: Dict, fallback: Dict, conversation_text: str) -> Dict:
    """Guardrails: shape, known sources, and mandatory security escalation."""
    decision = dict(fallback)  # start from the deterministic decision
    if not isinstance(raw, dict) or not raw.get("response"):
        raise llm.LLMError("LLM response missing required fields")

    decision["response"] = str(raw["response"]).strip()
    decision["category"] = raw.get("category", fallback["category"])
    decision["intent"] = raw.get("intent", fallback["intent"])
    decision["action"] = raw.get("action") if raw.get("action") in VALID_ACTIONS else fallback["action"]
    decision["priority"] = (
        raw.get("priority") if raw.get("priority") in VALID_PRIORITIES else fallback["priority"]
    )
    decision["assigned_team"] = raw.get("assigned_team") or fallback["assigned_team"]
    decision["policy_conflict"] = raw.get("policy_conflict") or fallback.get("policy_conflict")
    decision["issue_summary"] = raw.get("issue_summary") or fallback.get("issue_summary")
    try:
        decision["confidence"] = min(max(float(raw.get("confidence", 0.75)), 0.0), 1.0)
    except (TypeError, ValueError):
        decision["confidence"] = 0.75

    # Only KB ids that actually exist may be cited.
    source_ids = [s for s in (raw.get("source_ids") or []) if store.kb_by_id(s)]
    decision["source_ids"] = source_ids or fallback["source_ids"]

    decision["needs_follow_up"] = bool(raw.get("needs_follow_up")) or decision["action"] == "FOLLOW_UP"
    decision["follow_up_question"] = raw.get("follow_up_question") or (
        fallback.get("follow_up_question") if decision["needs_follow_up"] else None
    )
    decision["escalation_required"] = bool(raw.get("escalation_required")) or decision["action"] == "ESCALATE"
    decision["ticket_required"] = bool(raw.get("ticket_required")) or decision["action"] in {
        "CREATE_TICKET",
        "ESCALATE",
    }

    # Hard guardrail: a security incident is always HIGH + escalated + KB-09.
    if SECURITY_PATTERN.search(conversation_text):
        decision.update(
            {
                "category": "Security Incident",
                "action": "ESCALATE",
                "priority": "HIGH",
                "escalation_required": True,
                "ticket_required": True,
                "assigned_team": "Security",
                "needs_follow_up": False,
                "follow_up_question": None,
            }
        )
        if "KB-09" not in decision["source_ids"]:
            decision["source_ids"] = ["KB-09"] + decision["source_ids"]
        if rules.SECURITY_EMAIL not in decision["response"]:
            decision["response"] += (
                f"\n\nReport this immediately to {rules.SECURITY_EMAIL} and do not forward the email "
                "to other employees."
            )

    # Never allow "resolved" language on an escalated case.
    if decision["action"] == "ESCALATE":
        decision["response"] = re.sub(
            r"\bI have resolved\b|\bthis is resolved\b",
            "this is escalated (not resolved)",
            decision["response"],
            flags=re.IGNORECASE,
        )
    return decision


def handle_message(
    message: str,
    session_id: Optional[str] = None,
    employee: Optional[str] = None,
    email: Optional[str] = None,
    request_id: Optional[str] = None,
    auto_create_ticket: bool = True,
) -> Dict:
    if not message or not message.strip():
        raise ValueError("Message cannot be empty")

    session_id = session_id or f"sess-{uuid.uuid4().hex[:8]}"
    session = store.get_session(session_id)
    employee = employee or session.get("employee") or "Demo Employee"
    email = email or session.get("email")
    session["employee"] = employee
    session["email"] = email
    request_id = request_id or session.get("request_id")
    if request_id:
        session["request_id"] = request_id

    conversation_text = _conversation_text(session, message)

    audit_service.log(
        "Request received", detail=message[:240], session_id=session_id, actor="Employee"
    )

    # ---- Step 1-4: deterministic classification, retrieval and slot filling ----
    fallback = rules.decide(conversation_text, message, session)
    audit_service.log(
        "Classified request",
        detail=f"Category: {fallback['category']} | Intent: {fallback['intent']}",
        session_id=session_id,
    )
    retrieved = fallback["source_ids"] or retrieval.search_ids(conversation_text, 2)
    audit_service.log(
        "Knowledge base retrieval",
        detail=", ".join(retrieved) if retrieved else "No matching policy found in the knowledge base",
        session_id=session_id,
    )

    decision = fallback
    mode = llm.mode()

    # ---- Step 5: LLM reasoning (if configured), with deterministic fallback ----
    if llm.config.enabled:
        try:
            articles = store.kb_many(retrieved) or store.knowledge_base
            context = llm.build_context(
                articles, retrieval.precedents(fallback["category"]), session.get("slots", {})
            )
            conversation = session["history"] + [{"role": "user", "content": message}]
            raw = llm.ask(conversation, context)
            decision = _validate_llm_decision(raw, fallback, conversation_text)
            audit_service.log(
                "LLM decision validated against guardrails",
                detail=f"model={llm.config.model} action={decision['action']}",
                session_id=session_id,
            )
        except llm.LLMError as exc:
            mode = "mock-fallback"
            decision = fallback
            audit_service.log(
                "LLM unavailable - deterministic policy engine used",
                detail=str(exc)[:200],
                session_id=session_id,
            )

    audit_service.log(
        "Decision taken",
        detail=(
            f"Action: {decision['action']} | Priority: {decision['priority']} | "
            f"Confidence: {decision['confidence']:.2f}"
        ),
        session_id=session_id,
    )
    if decision.get("policy_conflict"):
        audit_service.log(
            "Policy conflict flagged - routed for human approval",
            detail=decision["policy_conflict"],
            session_id=session_id,
        )

    # ---- Step 6: act ----
    ticket = None
    if decision["ticket_required"] and auto_create_ticket:
        status = decision.get("ticket_status") or STATUS_FOR_ACTION.get(decision["action"], "New")
        ticket = ticket_service.create_ticket(
            employee=employee,
            email=email,
            category=decision["category"],
            issue_summary=decision.get("issue_summary") or message[:140],
            priority=decision["priority"],
            status=status,
            assigned_team=decision["assigned_team"],
            source_ids=decision["source_ids"],
            action_taken=decision["response"][:500],
            request_id=request_id,
        )
        audit_service.log(
            f"Ticket {ticket['ticket_id']} created",
            detail=f"Status: {status} | Team: {decision['assigned_team']}",
            session_id=session_id,
            ticket_id=ticket["ticket_id"],
        )
        if decision["escalation_required"]:
            audit_service.log(
                f"Escalated to {decision['assigned_team']}",
                detail="Escalation required by policy - awaiting human action",
                session_id=session_id,
                ticket_id=ticket["ticket_id"],
            )
        audit_service.attach_session_events_to_ticket(session_id, ticket["ticket_id"])
        if request_id:
            store.update_request(
                request_id,
                agent_status=f"{decision['action']} - {ticket['ticket_id']}",
                ticket_id=ticket["ticket_id"],
            )
    elif request_id:
        store.update_request(request_id, agent_status=decision["action"])

    if decision["action"] == "RESOLVE" and not ticket:
        audit_service.log(
            "Resolved without a ticket",
            detail="Self-service resolution provided from policy",
            session_id=session_id,
        )
    if decision["action"] == "FOLLOW_UP":
        audit_service.log(
            "Follow-up question asked",
            detail=decision.get("follow_up_question") or decision["response"],
            session_id=session_id,
        )

    # ---- Step 7: update conversation memory ----
    session["history"].append({"role": "user", "content": message})
    session["history"].append({"role": "assistant", "content": decision["response"]})

    sources = store.kb_many(decision["source_ids"])
    return {
        "session_id": session_id,
        "decision": {k: v for k, v in decision.items() if k not in {"pending_slot", "ticket_status", "issue_summary"}},
        "sources": sources,
        "ticket": ticket,
        "audit": audit_service.for_session(session_id),
        "mode": mode,
    }


def process_request(request_id: str) -> Dict:
    """Run the agent over one of the seeded employee requests (REQ-01..15)."""
    req = store.get_request(request_id)
    if not req:
        raise KeyError(request_id)
    return handle_message(
        message=req["request"],
        session_id=f"req-{request_id.lower()}",
        employee=req["employee"],
        email=req["email"],
        request_id=request_id,
    )
