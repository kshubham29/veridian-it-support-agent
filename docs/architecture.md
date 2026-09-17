# Architecture — Veridian Internal IT Service Agent

## 1. Process flow

```
Employee
   ↓
React UI  (AI Support chat, Requests inbox)
   ↓  POST /api/chat
FastAPI  (routes/api.py — validation, error handling)
   ↓
Agent Orchestrator  (services/agent.py)
   ↓
Intent Classification  (services/rules.py — 12 categories, regex/lexical)
   ↓
Knowledge Retrieval  (services/retrieval.py — KB-01…KB-10 + ASSET-01, precedent tickets)
   ↓
LLM  (services/llm.py — optional, OpenAI-compatible, strict JSON)
   ↓
Decision Engine  (guardrail validation in agent.py, deterministic fallback in rules.py)
   ↓
Resolve  /  Follow-up  /  Escalate
   ↓
Ticket Service  (services/ticket_service.py)
   ↓
Audit Service  (services/audit_service.py)
   ↓
Structured JSON response → rendered by the UI (answer + badges + source card + ticket link)
```

## 2. Components

### Knowledge base (`data/knowledge_base.json`)
Eleven policy records: KB-01 … KB-10 from the data pack plus `ASSET-01`, the Asset Management Policy
extract. Each record carries `id`, `title`, `category`, verbatim `text` and retrieval `keywords`.
This file is the **only** policy source in the system — no policy text is embedded in prompts,
code branches or UI copy beyond what the retrieval layer returns.

**Retrieval** is lexical scoring: exact phrase keyword matches (weight 3), single-token keyword
matches (2), title-token matches (1.5) and body-overlap (0.2 × overlapping tokens). With 11 short
policies this is faster, fully explainable and easier to defend in a demo than an embedding index.

### Ticket history (`data/tickets.json`)
TK-1042 … TK-1051 loaded at startup with an `is_active` flag derived from the data pack
(Resolved / Rejected / Approved-closed → inactive). Closed tickets are surfaced to the agent only as
**precedent** (e.g. TK-1043 for a 3.2-year laptop, TK-1050 for a rejected admin-access request) and
are never treated as work in progress. Seeded tickets also receive two synthetic audit events so the
Ticket Detail page is never empty.

### Employee requests (`data/employee_requests.json`)
REQ-01 … REQ-15 form the demo inbox. Each row can be opened in the chat (pre-filled, identity
attached) or processed in one click via `POST /api/requests/{id}/process`, which runs the same agent
pipeline and writes the resulting `agent_status` and `ticket_id` back onto the request.

### LLM layer (`services/llm.py`)
A single provider abstraction over the OpenAI-compatible `/chat/completions` contract, configured
purely by environment variables (`LLM_PROVIDER`, `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`,
`LLM_TIMEOUT`). Swapping OpenAI for Azure OpenAI, Groq, OpenRouter, Ollama or vLLM is a config
change, not a code change. The system prompt contains the hard rules; the user-side context block
contains only retrieved policies, precedent tickets and facts already collected in the conversation.

### Decision engine (`services/rules.py`)
Per-category rules that map (category + collected slots) → decision. Required slots per category:

| Category | Required facts | Follow-up asked when missing |
|---|---|---|
| Laptop/Hardware | age in years, verified hardware failure | "How old is the laptop…?" / "Is there a verified hardware failure…?" |
| VPN | full-time vs contractor, or expiry symptom | "Is the VPN showing an expired credential message?" / "full-time employee or a contractor?" |
| Software | catalog vs non-catalog | "Is the software listed in the approved software catalog?" |
| Printer | spooler restarted, asset tag | "Have you already… restarted the print spooler?" → "What is the printer's asset tag?" |
| Finance/Expense | does an account already exist | "Do you already have an expense tool account…?" |
| WFH Equipment | remote days per week | "How many days per week are you working remotely?" |
| Unknown | the actual service affected | "What isn't working — your laptop, VPN, email, printer, software…?" |

Slots are extracted from the whole conversation, and a short reply ("yes", "PRN-3045") is
interpreted against the last question asked, so the agent never re-asks what it already knows.

### Source attribution
Every decision returns `source_ids`; the API resolves them to full policy records, and the UI renders
an expandable **Source** card with the verbatim policy text (plus issuer and last-updated for the
Asset Management Policy). If nothing in the knowledge base covers the request, the UI explicitly
states that no policy applies rather than hiding the gap.

### Guardrails (`services/agent.py` + `rules.py`)
1. Only KB ids that exist in the knowledge base may be cited — LLM-invented ids are stripped.
2. Security keywords force `category=Security Incident`, `priority=HIGH`, `action=ESCALATE`,
   `source=KB-09`, `team=Security`, plus the "do not forward / report to security@…" instruction.
3. "Resolved" phrasing is rewritten on escalated cases; escalation never presents as resolution.
4. Tickets are created by `ticket_service`, and the returned `ticket` object is what the UI renders —
   the agent cannot claim a ticket that does not exist.
5. Missing required facts produce exactly one follow-up question instead of an assumption.
6. Invalid action/priority values, malformed JSON, HTTP errors and timeouts fall back to the
   deterministic engine, and the fallback itself is audited.
7. Closed tickets are only ever passed as precedent context.
8. Where two policies conflict (KB-03 vs ASSET-01), both sources are shown, a `policy_conflict`
   field is populated, the case is routed for IT approval **and** Finance sign-off, and the ticket is
   left in `Pending Approval` — the agent does not pick a winner.

### Audit trail (`services/audit_service.py`)
Append-only events with id, timestamp, actor, event and detail. A typical escalation produces:
`Request received` → `Classified request` → `Knowledge base retrieval` → `Decision taken` →
`Ticket TK-AUTO-00n created` → `Escalated to Security`. Events raised during a chat turn are
back-filled onto the ticket created in that turn, so the Ticket Detail page shows the complete
reasoning chain. Manual actions (resolve/escalate from the UI) are logged with `actor=User`.

## 3. Data model

`Ticket`: ticket_id · request_id · employee · email · category · issue_summary · priority · status ·
is_active · assigned_team · action_taken · source_ids · created_at · updated_at · origin

`AgentDecision`: category · intent · response · action · priority · source_ids · needs_follow_up ·
follow_up_question · ticket_required · escalation_required · assigned_team · confidence ·
policy_conflict · precedent_ticket_ids

`AuditEvent`: id · ticket_id · session_id · timestamp · actor · event · detail

Statuses: New · In Progress · Resolved · Escalated · Pending Approval · Pending Employee · Rejected.
Active statuses (everything except Resolved/Rejected) drive the dashboard's open-ticket counter.

## 4. Deployment shape

Two processes: `uvicorn` on :8000 and Vite on :5173 with `/api` proxied. State lives in memory and is
mirrored to `data/runtime_state.json`; `POST /api/reset` restores seed state between demo runs.
