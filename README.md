# Veridian Corp — Internal IT Service Agent

An AI-powered internal IT support agent for Veridian Corp. It understands an employee's issue,
retrieves the governing company policy, asks a follow-up question when a fact is missing, resolves
simple requests, escalates risky or unclear ones, creates structured tickets, **shows the source it
used**, and writes an audit trail for every action.

Built for the AIONOS *Agentic AI Factory — Assignment 2 (Internal Service Agent)* brief.

---

## 1. Project overview

| | |
|---|---|
| **Domain** | Corporate IT support (Veridian Corp, week of 21–25 Sep 2026) |
| **Frontend** | React 18 + TypeScript + Vite + Tailwind CSS + lucide-react |
| **Backend** | Python 3.11+ + FastAPI |
| **Data** | JSON seed files (`/data`) loaded into an in-memory store |
| **AI** | Any OpenAI-compatible LLM; **deterministic Demo Mode when no API key is set** |

## 2. Problem statement

Veridian's IT service desk receives free-text employee requests that mix trivial self-service
questions ("how do I get guest Wi-Fi?") with approval-gated requests (contractor VPN, laptop
replacement) and genuine security incidents (phishing). Humans triage each one manually,
policy answers are inconsistent, and there is no trace of *why* a decision was taken.

The agent automates triage while staying auditable: every answer is grounded in a named policy,
every decision is logged, and anything risky or unclear goes to a human instead of being guessed.

## 3. Features

- **AI chat interface** with category, action, priority, assigned team and confidence on every reply
- **Grounded answers** — expandable source card showing the exact policy text used (KB-01 … KB-10, Asset Management Policy)
- **Follow-up questions** — one concise question when a required fact is missing (laptop age, contractor vs full-time, catalog status, printer asset tag, remote days/week, whether an expense account exists)
- **Escalation logic** — phishing/malware/unauthorised access is forced to HIGH priority, KB-09, Security team, ticket + escalation
- **Policy decision point handling** — KB-03 (3-year replacement) vs the Asset Management Policy (4-year refresh, Finance sign-off for early replacement) is surfaced with **both** sources and routed for approval, never silently reconciled
- **Structured tickets** with the full field set, status chips and filters
- **Audit trail** per ticket (request received → classified → KB retrieved → decision → conflict flagged → ticket created → escalated)
- **Employee Requests inbox** (REQ-01 … REQ-15) with "Open in AI Agent" and one-click "Run agent"
- **Ticket history** (TK-1042 … TK-1051) — closed tickets are used as precedent only, never as active cases
- **Demo Mode** — full functionality with no API key; graceful fallback if the LLM fails or times out

## 4. Architecture

```
Employee → React UI → FastAPI → Agent Orchestrator
                                   ├── Intent classification (rules.py)
                                   ├── Knowledge retrieval (retrieval.py)
                                   ├── LLM reasoning (llm.py, optional)
                                   ├── Guardrail validation (agent.py)
                                   ├── Decision: Resolve / Follow-up / Ticket / Escalate
                                   ├── Ticket service (ticket_service.py)
                                   └── Audit service (audit_service.py)
```

Full detail, including the guardrail list and data-flow diagram: [`docs/architecture.md`](docs/architecture.md).

## 5. Agent workflow

1. **Receive** the message and log `Request received`.
2. **Classify** into one of 12 categories (Password, VPN, Laptop/Hardware, Software, Printer,
   Email/Mailbox, Guest Wi-Fi, Security Incident, Finance/Expense, Access Request, WFH Equipment, Unknown).
3. **Retrieve** the governing policies by lexical scoring over the knowledge base.
4. **Check completeness** — if a required slot is missing, ask exactly one follow-up question.
5. **Decide** — `RESOLVE`, `CREATE_TICKET`, `ESCALATE`, or `FOLLOW_UP` (+ priority and assigned team).
6. **Act** — the backend creates the ticket; the response text never claims a ticket that does not exist.
7. **Show the source** — KB ids are returned with full policy text for display.
8. **Audit** — every step above becomes an immutable audit event attached to the ticket.

## 6. Tech stack

`React 18` · `TypeScript` · `Vite` · `Tailwind CSS` · `lucide-react` · `react-router-dom`
`Python 3.11+` · `FastAPI` · `Pydantic v2` · `httpx` · `uvicorn` · JSON data store · `pytest`

## 7. Setup instructions

**Backend** (terminal 1):

```bash
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                   # optional — Demo Mode works without it
uvicorn app.main:app --reload --port 8000
```

API: <http://localhost:8000> · Swagger docs: <http://localhost:8000/docs>

**Frontend** (terminal 2):

```bash
cd frontend
npm install
npm run dev
```

UI: <http://localhost:5173> (Vite proxies `/api` to `http://localhost:8000`).

**Tests**:

```bash
cd backend && python -m pytest -q      # 20 acceptance tests incl. all five demo scenarios
```

## 8. Environment variables

All optional — the app runs in Demo Mode with none of them set.

| Variable | Default | Purpose |
|---|---|---|
| `LLM_API_KEY` | *(empty)* | Set to enable real LLM mode |
| `LLM_PROVIDER` | `openai` | Label for the provider in use |
| `LLM_BASE_URL` | `https://api.openai.com/v1` | Any OpenAI-compatible endpoint (Azure OpenAI, Groq, OpenRouter, Ollama, vLLM) |
| `LLM_MODEL` | `gpt-4o-mini` | Model name |
| `LLM_TIMEOUT` | `20` | Seconds before falling back to the deterministic engine |
| `CORS_ORIGINS` | `http://localhost:5173` | Allowed browser origins |
| `VITE_API_BASE` | *(empty)* | Frontend override if the API is not proxied |

## 9. Mock mode (Demo Mode)

With no `LLM_API_KEY`, `services/rules.py` acts as the agent: a deterministic policy engine with
classification, slot filling, follow-up questions and the same guardrails. The UI shows a
**Demo Mode** badge. This is the mode the acceptance tests run in, so a reviewer can clone and run
the project with zero credentials.

## 10. Real LLM mode

Set `LLM_API_KEY` (and optionally `LLM_BASE_URL` / `LLM_MODEL`) and restart the API. The agent then
builds a context block containing only the retrieved policies, historical ticket precedent and the
facts already collected, and asks the model for a strict JSON decision. The response is validated
before it reaches the user:

- unknown or invented KB ids are stripped; only real policy ids survive
- invalid actions/priorities fall back to the deterministic decision
- security incidents are forced to HIGH / ESCALATE / KB-09 / Security regardless of model output
- "resolved" phrasing is rewritten on escalated cases
- any timeout, HTTP error or malformed JSON falls back to Demo Mode and is written to the audit trail

## 11. API endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/health` | Status + active agent mode |
| `POST` | `/api/chat` | Main agent endpoint (structured decision, sources, ticket, audit) |
| `GET` | `/api/tickets` | Ticket queue (`status`, `category`, `priority`, `search` filters) |
| `POST` | `/api/tickets` | Create a ticket manually |
| `GET` | `/api/tickets/{ticket_id}` | Single ticket |
| `POST` | `/api/tickets/{ticket_id}/resolve` | Mark resolved |
| `POST` | `/api/tickets/{ticket_id}/escalate` | Escalate to a team |
| `GET` | `/api/audit/{ticket_id}` | Audit trail for a ticket |
| `GET` | `/api/audit?limit=n` | Recent audit events |
| `GET` | `/api/requests` | Employee requests REQ-01…REQ-15 |
| `POST` | `/api/requests/{id}/process` | Run the agent over a seeded request |
| `GET` | `/api/knowledge-base?q=` | Searchable policy list |
| `GET` | `/api/knowledge-base/{kb_id}` | Single policy |
| `GET` | `/api/dashboard/stats` | Counters + recent activity |
| `POST` | `/api/reset` | Reset runtime data to seed state |

Example response from `POST /api/chat`:

```json
{
  "category": "VPN",
  "intent": "credential_expired",
  "response": "VPN credentials expire every 90 days…",
  "action": "RESOLVE",
  "priority": "MEDIUM",
  "source_ids": ["KB-02"],
  "needs_follow_up": false,
  "follow_up_question": null,
  "ticket_required": false,
  "escalation_required": false,
  "assigned_team": "IT Service Desk",
  "confidence": 0.93
}
```

## 12. Demo scenarios

| # | Say this in AI Support | Agent behaviour |
|---|---|---|
| 1 | *"I'm locked out of my account. I tried my password 6 times."* | KB-01 · manual IT unlock explained · ticket (In Progress, IT Service Desk) · audit trail |
| 2 | *"I received an email asking for my login. Should I forward it to my teammates?"* | KB-09 · HIGH · "do not forward" · security@veridian-corp.example · escalated to Security + ticket |
| 3 | *"My new contractor needs VPN access."* | KB-02 · manager approval via access request form · ticket Pending Approval (IT Access Management) |
| 4 | *"My laptop won't turn on and I've had it for 3.5 years."* | KB-03 **and** Asset Management Policy shown · conflict flagged · routed for IT approval + Finance sign-off · Pending Approval |
| 5 | *"My mailbox is full and I can't send emails."* | KB-06 · 25GB default · archive advice · increase needs manager approval, capped at 50GB · no ticket |

Bonus: *"hey can you help, its not working"* → clarifying question, no guessing.
Full walkthrough with timings: [`docs/demo-script.md`](docs/demo-script.md).

## 13. Data sources

Everything comes from the assignment data pack, stored in `/data`:

- `knowledge_base.json` — KB-01 … KB-10 plus the Asset Management Policy extract (`ASSET-01`)
- `employee_requests.json` — REQ-01 … REQ-15 with employee, email, date and initial action
- `tickets.json` — TK-1042 … TK-1051 with active/closed flags

No other policy content is used anywhere in the codebase or the prompts.

## 14. Assumptions

1. Team names (`IT Service Desk`, `IT Security`, `IT Access Management`, `IT Hardware`, `Finance`, `Security`) are routing labels, not policy claims.
2. "Approved (closed)" tickets in the data pack are treated as closed history; `TK-1043`, `TK-1044`, `TK-1047`, `TK-1048` remain active.
3. Seeded tickets were given plausible emails and timestamps inside the 21–25 Sep 2026 window so the queue renders; issue text and status are verbatim from the data pack.
4. Privileged/admin server access (REQ-10) is **not** covered by any supplied policy, so the agent says so explicitly and escalates rather than inventing an approval path.
5. Auto-generated tickets use the `TK-AUTO-nnn` series to stay distinguishable from the legacy `TK-10xx` records.
6. Session memory is in-process; restarting the backend clears conversations (tickets and audit events are mirrored to `data/runtime_state.json`).

## 15. AI tools used

- **Microsoft 365 Copilot (Claude Opus 5)** — requirement analysis from the brief and data pack, architecture design, generation of the FastAPI service layer, the policy/rules engine, the React + Tailwind UI, the tests and this documentation.
- **OpenAI-compatible LLM (runtime, optional)** — powers the agent's reasoning in LLM mode via `backend/app/services/llm.py`; the deterministic engine remains the fallback and the guardrail validator.

## 16. Limitations

- Lexical (keyword/BM25-style) retrieval, not embeddings — fine for 11 short policies, would need a vector index at real corpus size.
- JSON/in-memory persistence, no database, no authentication, no RBAC.
- Conversation memory is per-session and in-process; there is no cross-session employee history.
- No real integrations (Active Directory unlock, mailbox quota API, asset register) — the agent routes, it does not execute changes in downstream systems.
- LLM mode quality depends on the configured model; guardrails constrain it but cannot fully prevent awkward phrasing.
- No automated frontend tests; acceptance testing is at the API/agent layer (20 tests).

## 17. Future improvements

- Vector retrieval with policy chunking and citation highlighting at sentence level
- Real approval workflow (manager/Finance sign-off callbacks) with SLA timers
- Postgres persistence + auth/RBAC and per-employee history
- Integrations: AD account unlock, mailbox quota API, asset register lookup for automatic laptop age
- Analytics: deflection rate, escalation accuracy, follow-up efficiency, policy-conflict frequency
- Human-in-the-loop review queue for low-confidence decisions

---

### Project structure

```
veridian-it-agent/
├── backend/
│   ├── app/
│   │   ├── main.py                 FastAPI app, CORS, error handling
│   │   ├── routes/api.py           All REST endpoints
│   │   ├── schemas/models.py       Pydantic contracts
│   │   └── services/
│   │       ├── agent.py            Orchestrator (classify → retrieve → decide → act → audit)
│   │       ├── rules.py            Deterministic policy engine + guardrails (Demo Mode)
│   │       ├── retrieval.py        Knowledge base retrieval & precedent lookup
│   │       ├── llm.py              Pluggable OpenAI-compatible provider
│   │       ├── ticket_service.py   Ticket lifecycle
│   │       ├── audit_service.py    Audit trail
│   │       └── store.py            JSON-backed in-memory store
│   ├── tests/test_agent.py         20 acceptance tests
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── components/             Sidebar, badges, source card, states
│       ├── pages/                  Dashboard, Chat, Tickets, TicketDetail, Requests, KnowledgeBase, Settings
│       ├── services/api.ts         Typed API client with error handling
│       ├── hooks/useToast.tsx      Toast notifications
│       ├── data/demoScenarios.ts   Quick-launch demo prompts
│       └── types/index.ts
├── data/                           knowledge_base.json · employee_requests.json · tickets.json
└── docs/                           architecture.md · demo-script.md
```
