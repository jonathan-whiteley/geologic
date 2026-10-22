import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ShieldAlert, X } from 'lucide-react'
import { api } from '../api/client'

const POINTS: { key: 'ingest' | 'suggest' | 'publish'; label: string }[] = [
  { key: 'ingest', label: 'Ingest: quarantined by the Lakeflow pipeline' },
  { key: 'suggest', label: 'Draft: blocked by the policy check' },
  { key: 'publish', label: 'Publish: refused by the publish re-check' },
]

/** Audit trail for quarantined moments: rule, reason and enforcement points only. The post is never fetched or shown. */
export default function QuarantineTrail({ onClose }: { onClose: () => void }) {
  const { data, isLoading, isError } = useQuery({ queryKey: ['quarantine'], queryFn: api.quarantine })

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const count = data?.count ?? 0
  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-surface-secondary/70 backdrop-blur-sm" onClick={onClose}>
      <div role="dialog" aria-modal="true" aria-labelledby="qt-title" className="card w-full max-w-lg p-6 space-y-4 shadow-strong" onClick={e => e.stopPropagation()}>
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-xl bg-red-50 text-red-700 flex items-center justify-center shrink-0"><ShieldAlert className="w-5 h-5" /></div>
          <div className="flex-1">
            <h3 id="qt-title" className="font-semibold">{count} {count === 1 ? 'moment' : 'moments'} quarantined by policy</h3>
            {data && (data.rule_id || data.reason) && <p className="text-sm text-text-secondary">{[data.rule_id, data.reason].filter(Boolean).join(' · ')}</p>}
          </div>
          <button type="button" className="p-1.5 rounded-lg hover:bg-gray-100 text-text-secondary" onClick={onClose} aria-label="Close"><X className="w-4 h-4" /></button>
        </div>
        {isLoading && <p className="text-sm text-text-tertiary">Loading the audit trail...</p>}
        {isError && <p className="text-sm text-red-600">Couldn&apos;t load the audit trail.</p>}
        {data && (
          <ol className="space-y-2">
            {POINTS.map((p, i) => {
              const hit = data.points.find(x => x.enforcement_point === p.key)
              return (
                <li key={p.key} className="flex items-start gap-3 rounded-xl border border-gray-100 bg-surface-secondary px-3 py-2.5">
                  <span className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-semibold shrink-0 ${hit ? 'bg-red-50 text-red-700' : 'bg-gray-100 text-text-tertiary'}`}>{i + 1}</span>
                  <div className="text-sm">
                    <p className="font-medium">{p.label}</p>
                    <p className="text-xs text-text-tertiary">{hit ? new Date(hit.occurred_at).toLocaleString() : 'No event recorded'}</p>
                  </div>
                </li>
              )
            })}
          </ol>
        )}
        <p className="text-xs text-text-tertiary">The post itself is never shown.</p>
      </div>
    </div>
  )
}
