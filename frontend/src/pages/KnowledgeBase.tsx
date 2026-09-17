import { useCallback, useEffect, useState } from 'react'
import { BookOpen, Search } from 'lucide-react'
import { EmptyState, ErrorState, Loading, PageHeader } from '../components/States'
import { api, ApiError } from '../services/api'
import type { KBArticle } from '../types'

export default function KnowledgeBase() {
  const [articles, setArticles] = useState<KBArticle[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [query, setQuery] = useState('')

  const load = useCallback(() => {
    setError(null)
    api
      .knowledgeBase(query)
      .then(setArticles)
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Failed to load knowledge base.'))
  }, [query])

  useEffect(() => {
    const t = setTimeout(load, 150)
    return () => clearTimeout(t)
  }, [load])

  return (
    <div>
      <PageHeader
        title="Knowledge Base"
        subtitle="The only source of truth the agent is allowed to use"
      />
      <div className="p-6">
        <div className="card mb-4 p-4">
          <div className="relative">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
            <input
              className="input pl-9"
              placeholder="Search policies (e.g. vpn, quota, phishing)…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
        </div>

        {error ? (
          <ErrorState message={error} onRetry={load} />
        ) : !articles ? (
          <Loading label="Loading policies…" />
        ) : articles.length === 0 ? (
          <div className="card">
            <EmptyState title="No policy matches that search" hint="Try a different keyword." />
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {articles.map((a) => (
              <article key={a.id} className="card p-5">
                <div className="flex items-center gap-2">
                  <BookOpen className="h-4 w-4 text-brand-600" />
                  <span className="text-sm font-semibold text-brand-700">{a.id}</span>
                  <span className="chip bg-slate-100 text-slate-600">{a.category}</span>
                </div>
                <h2 className="mt-2 text-base font-semibold text-slate-900">{a.title}</h2>
                <p className="mt-2 text-sm leading-relaxed text-slate-600">{a.text}</p>
                {a.issued_by && (
                  <p className="mt-3 text-xs text-slate-500">
                    Issued by {a.issued_by}
                    {a.last_updated ? ` · last updated ${a.last_updated}` : ''}
                  </p>
                )}
              </article>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
