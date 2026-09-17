import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  ArrowUpRight,
  Bot,
  CheckCircle2,
  Loader2,
  Send,
  ShieldAlert,
  Ticket as TicketIcon,
  AlertTriangle,
  User,
} from 'lucide-react'
import { ActionBadge, ModeBadge, PriorityBadge } from '../components/Badges'
import SourceCard from '../components/SourceCard'
import { useToast } from '../hooks/useToast'
import { api, ApiError } from '../services/api'
import { SCENARIOS } from '../data/demoScenarios'
import type { ChatMessage, ChatResponse } from '../types'


/** Minimal markdown: **bold** plus line breaks. Keeps the demo readable without a dependency. */
function RichText({ text }: { text: string }) {
  return (
    <>
      {text.split('\n').map((line, i) => (
        <p key={i} className={line.trim() === '' ? 'h-2' : 'mb-1 last:mb-0'}>
          {line.split(/(\*\*[^*]+\*\*)/g).map((part, j) =>
            part.startsWith('**') && part.endsWith('**') ? (
              <strong key={j} className="font-semibold text-slate-900">
                {part.slice(2, -2)}
              </strong>
            ) : (
              <span key={j}>{part}</span>
            ),
          )}
        </p>
      ))}
    </>
  )
}

export default function Chat() {
  const [params] = useSearchParams()
  const { push } = useToast()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [mode, setMode] = useState('mock')
  const [employee, setEmployee] = useState(params.get('employee') ?? 'Demo Employee')
  const [email, setEmail] = useState(params.get('email') ?? '')
  const [requestId, setRequestId] = useState<string | null>(params.get('request'))
  const bottomRef = useRef<HTMLDivElement>(null)
  const prefill = params.get('message')

  useEffect(() => {
    api
      .health()
      .then((h) => setMode(h.mode))
      .catch(() => setMode('offline'))
  }, [])

  useEffect(() => {
    if (prefill) setInput(prefill)
  }, [prefill])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, sending])

  async function send(text: string) {
    const clean = text.trim()
    if (!clean) {
      push('Type a message first.', 'error')
      return
    }
    setInput('')
    setMessages((prev) => [
      ...prev,
      { id: `u-${Date.now()}`, role: 'user', text: clean, timestamp: new Date().toISOString() },
    ])
    setSending(true)
    try {
      const res: ChatResponse = await api.chat({
        message: clean,
        session_id: sessionId,
        employee,
        email: email || null,
        request_id: requestId,
      })
      setSessionId(res.session_id)
      setMode(res.mode)
      setMessages((prev) => [
        ...prev,
        {
          id: `a-${Date.now()}`,
          role: 'agent',
          text: res.decision.response,
          decision: res.decision,
          sources: res.sources,
          ticket: res.ticket,
          timestamp: new Date().toISOString(),
        },
      ])
      if (res.ticket) push(`Ticket ${res.ticket.ticket_id} created (${res.ticket.status}).`, 'success')
      if (res.decision.escalation_required) push('Escalated — this case was not auto-resolved.', 'info')
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Unexpected error contacting the agent.'
      push(message, 'error')
      setMessages((prev) => [
        ...prev,
        {
          id: `e-${Date.now()}`,
          role: 'agent',
          text: `I could not process that request: ${message}`,
          timestamp: new Date().toISOString(),
        },
      ])
    } finally {
      setSending(false)
    }
  }

  async function createTicketFor(msg: ChatMessage) {
    if (!msg.decision) return
    try {
      const ticket = await api.createTicket({
        employee,
        email: email || null,
        category: msg.decision.category,
        issue_summary: msg.text.slice(0, 140),
        priority: msg.decision.priority,
        status: 'New',
        assigned_team: msg.decision.assigned_team,
        source_ids: msg.decision.source_ids,
        action_taken: 'Ticket raised manually from the AI chat.',
        request_id: requestId,
      })
      push(`Ticket ${ticket.ticket_id} created.`, 'success')
      setMessages((prev) =>
        prev.map((m) => (m.id === msg.id ? { ...m, ticket } : m)),
      )
    } catch (err) {
      push(err instanceof ApiError ? err.message : 'Ticket creation failed.', 'error')
    }
  }

  async function resolveTicket(msg: ChatMessage) {
    if (!msg.ticket) {
      push('Marked as resolved for this conversation — no ticket was needed.', 'success')
      return
    }
    try {
      const ticket = await api.resolveTicket(msg.ticket.ticket_id)
      push(`${ticket.ticket_id} marked Resolved.`, 'success')
      setMessages((prev) => prev.map((m) => (m.id === msg.id ? { ...m, ticket } : m)))
    } catch (err) {
      push(err instanceof ApiError ? err.message : 'Could not resolve ticket.', 'error')
    }
  }

  return (
    <div className="flex h-screen flex-col">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-white px-6 py-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-600 text-white">
            <Bot className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-lg font-semibold text-slate-900">Veridian IT Support Agent</h1>
            <p className="text-sm text-slate-500">AI-powered internal IT support</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <ModeBadge mode={mode} />
          {requestId && (
            <span className="chip bg-brand-50 text-brand-700">Working on {requestId}</span>
          )}
        </div>
      </div>

      {/* Identity + scenarios */}
      <div className="flex flex-wrap items-center gap-2 border-b border-slate-200 bg-slate-50 px-6 py-3">
        <input
          className="input w-44"
          value={employee}
          onChange={(e) => setEmployee(e.target.value)}
          placeholder="Employee name"
        />
        <input
          className="input w-64"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="employee@veridian-corp.example"
        />
        <div className="ml-auto flex flex-wrap gap-2">
          {SCENARIOS.map((s) => (
            <button
              key={s.label}
              className="chip border border-slate-300 bg-white text-slate-600 hover:border-brand-500 hover:text-brand-700"
              onClick={() => send(s.text)}
              disabled={sending}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>

      {/* Conversation */}
      <div className="flex-1 overflow-y-auto px-6 py-6">
        <div className="mx-auto max-w-3xl space-y-4">
          {messages.length === 0 && (
            <div className="card p-8 text-center">
              <Bot className="mx-auto h-8 w-8 text-brand-600" />
              <p className="mt-3 text-base font-semibold text-slate-800">How can I help?</p>
              <p className="mt-1 text-sm text-slate-500">
                Describe an IT issue in your own words. I answer from Veridian policy only, show the source I
                used, ask a follow-up if something is missing, and raise a ticket when one is needed.
              </p>
            </div>
          )}

          {messages.map((m) =>
            m.role === 'user' ? (
              <div key={m.id} className="flex justify-end gap-2 fade-in">
                <div className="max-w-[80%] rounded-2xl rounded-br-sm bg-brand-600 px-4 py-3 text-sm text-white">
                  {m.text}
                </div>
                <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-slate-200">
                  <User className="h-4 w-4 text-slate-600" />
                </div>
              </div>
            ) : (
              <div key={m.id} className="flex gap-2 fade-in">
                <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-brand-100">
                  <Bot className="h-4 w-4 text-brand-700" />
                </div>
                <div className="card max-w-[85%] p-4">
                  {m.decision && (
                    <div className="mb-3 flex flex-wrap items-center gap-2">
                      <span className="chip bg-slate-100 text-slate-700">{m.decision.category}</span>
                      <ActionBadge action={m.decision.action} />
                      <PriorityBadge priority={m.decision.priority} />
                      <span className="chip bg-slate-100 text-slate-500">
                        {m.decision.assigned_team}
                      </span>
                      <span className="ml-auto text-xs text-slate-400">
                        confidence {(m.decision.confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                  )}

                  <div className="text-sm leading-relaxed text-slate-700">
                    <RichText text={m.text} />
                  </div>

                  {m.decision?.policy_conflict && (
                    <div className="mt-3 flex gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3">
                      <AlertTriangle className="h-4 w-4 shrink-0 text-amber-600" />
                      <div className="text-xs text-amber-800">
                        <p className="font-semibold">Policy decision point — routed to a human</p>
                        <p>{m.decision.policy_conflict}</p>
                      </div>
                    </div>
                  )}

                  {m.decision?.escalation_required && (
                    <div className="mt-3 flex items-center gap-2 rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-800">
                      <ShieldAlert className="h-4 w-4 shrink-0" />
                      Escalated to {m.decision.assigned_team} — this case is <b>not</b> resolved.
                    </div>
                  )}

                  {m.sources && <SourceCard sources={m.sources} />}

                  {m.decision && m.decision.precedent_ticket_ids.length > 0 && (
                    <p className="mt-2 text-xs text-slate-500">
                      Precedent (history only): {m.decision.precedent_ticket_ids.join(', ')}
                    </p>
                  )}

                  {m.ticket && (
                    <Link
                      to={`/tickets/${m.ticket.ticket_id}`}
                      className="mt-3 flex items-center gap-2 rounded-lg border border-brand-200 bg-brand-50 px-3 py-2 text-sm text-brand-800 hover:bg-brand-100"
                    >
                      <TicketIcon className="h-4 w-4" />
                      <span className="font-medium">{m.ticket.ticket_id}</span>
                      <span className="text-brand-700">· {m.ticket.status}</span>
                      <span className="text-brand-700">· {m.ticket.assigned_team}</span>
                      <ArrowUpRight className="ml-auto h-4 w-4" />
                    </Link>
                  )}

                  {m.decision && (
                    <div className="mt-3 flex gap-2">
                      <button className="btn-secondary" onClick={() => resolveTicket(m)}>
                        <CheckCircle2 className="h-4 w-4" /> Resolve
                      </button>
                      <button
                        className="btn-secondary"
                        onClick={() => createTicketFor(m)}
                        disabled={!!m.ticket}
                      >
                        <TicketIcon className="h-4 w-4" />
                        {m.ticket ? 'Ticket created' : 'Create Ticket'}
                      </button>
                    </div>
                  )}
                </div>
              </div>
            ),
          )}

          {sending && (
            <div className="flex items-center gap-2 text-sm text-slate-500">
              <Loader2 className="h-4 w-4 animate-spin" /> Agent is checking company policy…
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      </div>

      {/* Composer */}
      <form
        className="border-t border-slate-200 bg-white px-6 py-4"
        onSubmit={(e) => {
          e.preventDefault()
          send(input)
        }}
      >
        <div className="mx-auto flex max-w-3xl items-center gap-2">
          <input
            className="input"
            placeholder="Describe your IT issue…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={sending}
          />
          <button className="btn-primary" type="submit" disabled={sending || !input.trim()}>
            {sending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
            Send
          </button>
        </div>
      </form>
    </div>
  )
}
