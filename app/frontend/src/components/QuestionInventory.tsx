import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import type { InventoryRow } from '../api/types'
import { PageSkeleton, ErrorRetry } from './PageState'
import { formatK } from '../lib/format'

type Filter = 'all' | 'absent' | 'wrong'
const FILTERS: { key: Filter; label: string; test: (r: InventoryRow) => boolean }[] = [
  { key: 'all', label: 'All', test: () => true },
  { key: 'absent', label: 'LCE absent', test: r => r.engines_answered > 0 && r.engines_naming === 0 },
  { key: 'wrong', label: 'Wrong claims', test: r => !!r.has_wrong_claim },
]

export default function QuestionInventory({ clusterLabel }: { clusterLabel: (c: string) => string }) {
  const navigate = useNavigate()
  const [filter, setFilter] = useState<Filter>('all')
  const { data, isLoading, isError, refetch } = useQuery({ queryKey: ['inventory'], queryFn: api.inventory })
  const rows = useMemo(() => (data ?? []).filter(FILTERS.find(f => f.key === filter)!.test), [data, filter])

  if (isLoading) return <PageSkeleton statCards={0} />
  if (isError || !data) return <ErrorRetry message="Couldn't load the tracked questions." onRetry={() => refetch()} />

  return (
    <div className="card p-6 space-y-4">
      <div className="flex items-end justify-between flex-wrap gap-3">
        <div>
          <h3 className="font-semibold">The buyer questions we track</h3>
          <p className="text-sm text-text-secondary">{data.length} questions, asked of every engine on every probe</p>
        </div>
        <div className="flex gap-1 bg-surface-tertiary rounded-xl p-1">
          {FILTERS.map(f => (
            <button key={f.key} onClick={() => setFilter(f.key)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium ${filter === f.key ? 'bg-white shadow-soft' : 'text-text-secondary'}`}>
              {f.label} <span className="text-text-tertiary tabular-nums">{data.filter(f.test).length}</span>
            </button>
          ))}
        </div>
      </div>
      <div className="overflow-auto max-h-[560px]">
        <table className="w-full text-sm">
          <thead className="text-left text-xs text-text-tertiary sticky top-0 bg-white">
            <tr><th className="py-2 pr-3">Question</th><th className="pr-3">Cluster</th><th className="pr-3 text-right">Volume/mo</th>
              <th className="pr-3">Type</th><th className="pr-3 text-right">Engines naming LCE</th><th className="pr-3 text-right">Share of Model</th><th /></tr>
          </thead>
          <tbody>
            {rows.map(r => (
              <tr key={r.prompt_id} onClick={() => navigate(`/measure/questions/${r.prompt_id}`)}
                className="border-t border-gray-100 hover:bg-gray-50 cursor-pointer">
                <td className="py-2.5 pr-3 font-medium">{r.prompt_text}</td>
                <td className="pr-3 text-text-secondary">{clusterLabel(r.cluster)}</td>
                <td className="pr-3 text-right tabular-nums">{r.avg_monthly_volume != null ? formatK(r.avg_monthly_volume) : 'N/A'}</td>
                <td className="pr-3"><span className="badge b-default">{r.branded ? 'Branded' : 'Unbranded'}</span></td>
                <td className={`pr-3 text-right tabular-nums ${r.engines_naming === 0 ? 'text-red-600 font-semibold' : ''}`}>{r.engines_naming} of {r.engines_answered}</td>
                <td className="pr-3 text-right tabular-nums">{r.answer_share != null ? r.answer_share.toFixed(2) : 'N/A'}</td>
                <td>{r.has_wrong_claim && <span className="badge b-error"><span className="dot" />Wrong claim</span>}</td>
              </tr>
            ))}
            {rows.length === 0 && <tr><td colSpan={7} className="py-8 text-center text-text-tertiary">No questions in this filter.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  )
}
