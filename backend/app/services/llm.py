"""Pluggable LLM provider layer.

Providers are OpenAI-compatible chat-completions endpoints, so OpenAI, Azure
OpenAI (with a compatible base URL), Groq, Together, OpenRouter or a local
Ollama/vLLM server all work by changing environment variables only:

    LLM_PROVIDER=openai
    LLM_API_KEY=sk-...
    LLM_BASE_URL=https://api.openai.com/v1
    LLM_MODEL=gpt-4o-mini

If LLM_API_KEY is absent the app runs in deterministic Demo (mock) mode.
"""
from __future__ import annotations

import json
import os
from typing import Dict, List, Optional

import httpx

SYSTEM_PROMPT = """You are the Veridian Corp internal IT Service Agent.

HARD RULES (a violation makes the answer unusable):
1. Use ONLY the company policies supplied in the CONTEXT block. Never invent a
   policy, an approval requirement, an SLA, an email address or a team name.
2. If no supplied policy covers the request, say so explicitly and escalate to a
   human instead of guessing.
3. Never claim a ticket was created - the backend creates tickets, not you.
4. Never say an issue is "resolved" when it was escalated or is awaiting approval.
5. Any suspected phishing, malware, unauthorised access or suspicious login is a
   HIGH priority Security Incident: tell the employee not to forward the email,
   give the reporting address from KB-09, and escalate.
6. If a required fact is missing (laptop age, contractor vs full-time, catalog
   status, asset tag, remote days per week, whether an account exists), ask ONE
   concise follow-up question instead of assuming.
7. If two supplied policies conflict, surface BOTH sources and route the case for
   the required approval. Do not silently pick one.
8. Closed tickets (Resolved / Rejected / Approved-closed) are historical
   precedent only - never treat them as active work.

Reply with ONLY a JSON object, no markdown fence, in this exact shape:
{
  "category": "Password|VPN|Laptop/Hardware|Software|Printer|Email/Mailbox|Guest Wi-Fi|Security Incident|Finance/Expense|Access Request|WFH Equipment|Unknown",
  "intent": "short_snake_case_intent",
  "response": "message shown to the employee",
  "action": "RESOLVE|FOLLOW_UP|CREATE_TICKET|ESCALATE",
  "priority": "LOW|MEDIUM|HIGH",
  "source_ids": ["KB-02"],
  "needs_follow_up": false,
  "follow_up_question": null,
  "ticket_required": false,
  "escalation_required": false,
  "assigned_team": "IT Service Desk",
  "confidence": 0.9,
  "policy_conflict": null,
  "issue_summary": "one line summary for the ticket"
}"""


class LLMConfig:
    def __init__(self) -> None:
        self.provider = os.getenv("LLM_PROVIDER", "openai")
        self.api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        self.model = os.getenv("LLM_MODEL", "gpt-4o-mini")
        self.timeout = float(os.getenv("LLM_TIMEOUT", "20"))

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)


config = LLMConfig()


def mode() -> str:
    return "llm" if config.enabled else "mock"


class LLMError(RuntimeError):
    pass


def build_context(articles: List[dict], precedent: List[dict], slots: Dict) -> str:
    policy_block = "\n".join(f"{a['id']} - {a['title']}: {a['text']}" for a in articles)
    precedent_block = (
        "\n".join(
            f"{t['ticket_id']} ({t['employee']}): {t['issue_summary']} -> {t['status']} "
            f"[{'active' if t.get('is_active') else 'closed'}]"
            for t in precedent
        )
        or "none"
    )
    known = json.dumps(slots) if slots else "{}"
    return (
        f"CONTEXT - COMPANY POLICIES (the only allowed source of truth):\n{policy_block}\n\n"
        f"HISTORICAL TICKETS (precedent only):\n{precedent_block}\n\n"
        f"FACTS ALREADY COLLECTED IN THIS CONVERSATION: {known}"
    )


def complete(messages: List[Dict[str, str]]) -> Dict:
    """Call the configured provider and return the parsed JSON decision."""
    if not config.enabled:
        raise LLMError("No LLM API key configured")
    payload = {
        "model": config.model,
        "messages": messages,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }
    headers = {"Authorization": f"Bearer {config.api_key}", "Content-Type": "application/json"}
    try:
        with httpx.Client(timeout=config.timeout) as client:
            resp = client.post(f"{config.base_url}/chat/completions", json=payload, headers=headers)
        if resp.status_code >= 400:
            raise LLMError(f"Provider returned {resp.status_code}: {resp.text[:200]}")
        content = resp.json()["choices"][0]["message"]["content"]
    except httpx.TimeoutException as exc:  # pragma: no cover - network path
        raise LLMError("LLM request timed out") from exc
    except (httpx.HTTPError, KeyError, ValueError) as exc:  # pragma: no cover
        raise LLMError(f"LLM call failed: {exc}") from exc

    content = content.strip()
    if content.startswith("```"):
        content = content.strip("`")
        content = content[content.find("{") :]
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise LLMError("LLM returned invalid JSON") from exc


def ask(conversation: List[Dict[str, str]], context: str) -> Optional[Dict]:
    messages = [{"role": "system", "content": SYSTEM_PROMPT + "\n\n" + context}]
    messages.extend(conversation[-8:])
    return complete(messages)
