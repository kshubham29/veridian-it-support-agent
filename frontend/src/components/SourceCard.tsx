import { useState } from 'react'
import { BookOpen, ChevronDown } from 'lucide-react'
import type { KBArticle } from '../types'

export default function SourceCard({ sources }: { sources: KBArticle[] }) {
  const [openId, setOpenId] = useState<string | null>(sources.length === 1 ? sources[0].id : null)

  if (!sources.length) {
    return (
      <p className="mt-2 text-xs italic text-slate-500">
        Source: no company policy in the knowledge base covers this request.
      </p>
    )
  }

  return (
    <div className="mt-3 space-y-2">
      <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">Source</p>
      {sources.map((s) => {
        const open = openId === s.id
        return (
          <div key={s.id} className="rounded-lg border border-slate-200 bg-slate-50">
            <button
              onClick={() => setOpenId(open ? null : s.id)}
              className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm font-medium text-slate-700"
            >
              <BookOpen className="h-4 w-4 text-brand-600" />
              <span>
                {s.id} — {s.title}
              </span>
              <ChevronDown
                className={`ml-auto h-4 w-4 text-slate-400 transition ${open ? 'rotate-180' : ''}`}
              />
            </button>
            {open && (
              <div className="border-t border-slate-200 px-3 py-2 text-sm leading-relaxed text-slate-600">
                {s.text}
                {s.issued_by && (
                  <p className="mt-2 text-xs text-slate-500">
                    Issued by {s.issued_by}
                    {s.last_updated ? ` · last updated ${s.last_updated}` : ''}
                  </p>
                )}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
