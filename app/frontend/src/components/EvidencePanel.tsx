import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, BadgeCheck, Database, ExternalLink, UserCheck } from 'lucide-react'
import { api } from '../api/client'

export default function EvidencePanel({ oppId }: { oppId: string }) {
  const { data, isLoading, isError } = useQuery({ queryKey: ['evidence', oppId], queryFn: () => api.evidence(oppId) })
  if (isLoading) return <div className="h-28 rounded-xl bg-surface-secondary animate-pulse" />
  if (isError || !data) return <p className="text-sm text-text-tertiary">Evidence unavailable right now.</p>
  const { wrong_claims, truth, cited_instead, signal, live_page } = data
  return (
    <div className="grid md:grid-cols-2 gap-4">
      {wrong_claims.length > 0 && (
        <div className="rounded-xl border border-red-100 bg-red-50/40 p-4">
          <p className="text-xs font-semibold text-red-700 mb-2 flex items-center gap-1.5"><AlertTriangle className="w-3.5 h-3.5" />What AI says</p>
          <ul className="space-y-1 text-sm">{wrong_claims.map((w, i) => <li key={i}><b>{w.engine}</b>: {w.item} at {w.price}</li>)}</ul>
        </div>
      )}
      {(truth || live_page) && (
        <div className="rounded-xl border border-green-100 bg-green-50/40 p-4 space-y-2">
          <p className="text-xs font-semibold text-green-700 flex items-center gap-1.5"><BadgeCheck className="w-3.5 h-3.5" />Source of truth</p>
          {truth && <p className="text-sm"><b>{truth.name}</b>: ${truth.price.toFixed(2)} <span className="text-text-tertiary">· menu, Unity Catalog</span></p>}
          {live_page && <p className="text-sm flex items-center gap-1.5"><Database className="w-3.5 h-3.5 text-text-tertiary" />Live page v{live_page.version} <span className="text-text-tertiary">· Lakebase</span></p>}
        </div>
      )}
      {cited_instead.length > 0 && (
        <div className="rounded-xl border border-gray-100 p-4">
          <p className="text-xs font-semibold text-text-secondary mb-2 flex items-center gap-1.5"><ExternalLink className="w-3.5 h-3.5" />What AI cites instead</p>
          <div className="flex flex-wrap gap-1.5">{cited_instead.map(c => <span key={c.publisher} className="badge b-default">{c.publisher} · {c.citations}</span>)}</div>
        </div>
      )}
      {signal && (
        <div className="rounded-xl border border-gray-100 p-4 flex gap-3">
          {signal.image_url && <img src={signal.image_url} alt={signal.persona_name ?? signal.author} className="w-20 h-20 rounded-lg object-cover" />}
          <div className="min-w-0 text-sm space-y-1">
            <p className="text-xs font-semibold text-text-secondary">The moment</p>
            <p><b>{signal.persona_name ?? signal.author}</b>{signal.menu_item_name && <> · matched to {signal.menu_item_name}</>}</p>
            <p className="text-text-secondary line-clamp-2">{signal.text}</p>
            {signal.persona_name && <p className="text-xs text-amber-700 flex items-center gap-1"><UserCheck className="w-3.5 h-3.5" />Person association: needs human review</p>}
            {signal.image_credit && <p className="text-[11px] text-text-tertiary">{signal.image_credit}</p>}
          </div>
        </div>
      )}
    </div>
  )
}
