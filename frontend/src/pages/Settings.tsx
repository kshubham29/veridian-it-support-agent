import { useCallback, useEffect, useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { ModeBadge } from '../components/Badges'
import { ErrorState, Loading, PageHeader } from '../components/States'
import { useToast } from '../hooks/useToast'
import { api, ApiError } from '../services/api'

export default function Settings() {
  const { push } = useToast()
  const [health, setHealth] = useState<{ status: string; mode: string; model: string | null } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    setError(null)
    api
      .health()
      .then(setHealth)
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Backend unreachable.'))
  }, [])

  useEffect(load, [load])

  async function reset() {
    setBusy(true)
    try {
      await api.reset()
      push('Demo data reset to seed state.', 'success')
    } catch (err) {
      push(err instanceof ApiError ? err.message : 'Reset failed.', 'error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      <PageHeader title="Settings" subtitle="Agent mode, data sources and demo controls" />
      <div className="p-6">
        {error ? (
          <ErrorState message={error} onRetry={load} />
        ) : !health ? (
          <Loading label="Checking backend…" />
        ) : (
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="card p-5">
              <h2 className="text-sm font-semibold text-slate-800">Agent mode</h2>
              <div className="mt-3 flex items-center gap-2">
                <ModeBadge mode={health.mode} />
                <span className="text-sm text-slate-600">
                  {health.mode === 'llm'
                    ? `Model: ${health.model}`
                    : 'No LLM API key configured — deterministic policy engine in use.'}
                </span>
              </div>
              <p className="mt-3 text-xs text-slate-500">
                Set <code className="rounded bg-slate-100 px-1">LLM_API_KEY</code> in{' '}
                <code className="rounded bg-slate-100 px-1">backend/.env</code> and restart the API to switch to
                LLM mode. Guardrails, retrieval, ticketing and audit logging are identical in both modes.
              </p>
            </div>

            <div className="card p-5">
              <h2 className="text-sm font-semibold text-slate-800">Data sources</h2>
              <ul className="mt-3 space-y-1 text-sm text-slate-600">
                <li>• data/knowledge_base.json — 10 KB policies + Asset Management Policy</li>
                <li>• data/employee_requests.json — REQ-01 … REQ-15</li>
                <li>• data/tickets.json — TK-1042 … TK-1051 (history)</li>
              </ul>
              <button className="btn-secondary mt-4" onClick={reset} disabled={busy}>
                <RefreshCw className="h-4 w-4" /> Reset demo data
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
