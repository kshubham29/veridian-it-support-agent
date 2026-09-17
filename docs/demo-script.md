# 15-Minute Demo Script

**Before you start:** backend on `:8000`, frontend on `:5173`, open **Settings → Reset demo data**,
then land on the Dashboard. Keep the Ticket Queue open in a second tab.

---

## 0:00 – 1:00 · The problem (1 min)

> "Veridian's IT desk gets free-text requests that mix trivial self-service questions with
> approval-gated requests and real security incidents. Triage is manual, policy answers are
> inconsistent, and there's no record of why a decision was made.
> This agent triages every request against company policy, shows the policy it used, asks a
> follow-up when something is missing, escalates anything risky, and logs every step."

Show the **Dashboard**: 15 requests, open/resolved/escalated/pending counters, recent activity.
Point out the **Demo Mode** badge — it runs with no API key, and an LLM can be switched on by config.

## 1:00 – 3:00 · Architecture (2 min)

Open `docs/architecture.md` (or the slide) and walk the flow in one pass:

> React UI → FastAPI → orchestrator → classification → knowledge retrieval → (LLM) →
> guardrail validation → resolve / follow-up / escalate → ticket service → audit service.

Three points to land: **grounding** (11 policies are the only source of truth), **guardrails**
(security forced to escalate, invented policy ids stripped, no fake tickets), **auditability**.

## 3:00 – 10:00 · Live demo (7 min)

Go to **AI Support**. Use the numbered quick-launch chips.

### Demo 1 — Password lockout (1 min)
Type: *"I'm locked out of my account. I tried my password 6 times."*
- Category **Password**, action **CREATE TICKET**, team IT Service Desk
- Expand **Source: KB-01** — read "locked out after 5 failed attempts… unlock manually"
- Note the agent says no approval is required, and a ticket appears with a live link

### Demo 2 — Phishing (1.5 min)
Type: *"I received an email asking for my login. Should I forward it to my teammates?"*
- Red escalation banner: **HIGH**, escalated to **Security**, *not* resolved
- Answer explicitly says **do not forward** and gives `security@veridian-corp.example`
- **Source: KB-09**; ticket created with status **Escalated**
- Click the ticket → show the audit trail (received → classified → KB-09 retrieved → decision →
  ticket created → escalated to Security)

### Demo 3 — Contractor VPN (1 min)
Type: *"My new contractor needs VPN access."*
- Agent recognises the contractor path: **manager approval via the access request form**
- Ticket **Pending Approval**, team IT Access Management, **Source: KB-02**
- Contrast: type *"My VPN isn't working."* → agent asks *"Is the VPN showing an expired credential
  message?"*; answer **Yes** → resolves with the 90-day renewal rule. One question, not five.

### Demo 4 — Laptop (2 min) — *the judgement call*
Type: *"My laptop won't turn on and I've had it for 3.5 years."*
- Amber **policy decision point** panel: KB-03 allows replacement at 3 years / verified hardware
  failure, but the Asset Management Policy sets a 4-year refresh cycle needing **Finance sign-off**
- Both sources are shown; the agent refuses to reconcile them silently
- Ticket **Pending Approval**, team **IT Hardware + Finance**, precedent **TK-1043** (3.2 yrs) cited
  as history only

### Demo 5 — Mailbox (1 min)
Type: *"My mailbox is full and I can't send emails."*
- **Source: KB-06**: 25GB default, archive old mail, increases need manager approval, capped at 50GB
- Action **RESOLVE**, **no ticket** — the agent doesn't create work that isn't needed

### Bonus — vague request (0.5 min)
Type: *"hey can you help, its not working"* → one clarifying question, no guessing, no source claimed.

## 10:00 – 13:00 · Tickets, audit trail, sources (3 min)

- **Ticket Queue**: filter Status = *Escalated*, then Category = *Laptop/Hardware*; search `TK-1043`
- Show that legacy tickets TK-1042…TK-1051 are loaded, and closed ones are labelled
  **"Closed — history only"**
- Open the phishing ticket → full field set (ID, request ID, employee, category, priority, status,
  team, action taken, source, timestamps) + audit timeline + expandable KB-09 text
- **Employee Requests**: click **Run agent** on REQ-11 (contractor VPN) — status updates in place and
  links to the created ticket
- **Knowledge Base**: search `quota` to show the policy corpus the agent is restricted to

## 13:00 – 15:00 · Technical notes and limitations (2 min)

- Modular service layer: `agent.py` orchestrates, `rules.py` decides, `retrieval.py` grounds,
  `llm.py` is swappable by env vars, `ticket_service.py` / `audit_service.py` act and record
- Demo Mode is deterministic and fully tested (`python -m pytest -q` → 20 tests, all five scenarios)
- LLM mode adds reasoning but never bypasses the guardrails; failures fall back and are audited
- Known limits: lexical retrieval, JSON store, no auth, no downstream integrations (AD unlock,
  mailbox API, asset register), per-session memory only
- Next: vector retrieval, real approval callbacks, Postgres + RBAC, deflection/escalation analytics

**Close:** "Every answer is traceable to a named policy, every action is on the audit trail, and
anything the policies don't settle goes to a human — that's the difference between a chatbot and a
service agent."
