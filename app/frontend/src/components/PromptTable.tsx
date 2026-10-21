import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ListChecks } from 'lucide-react'
import type { PromptRow } from '../api/types'
import { formatK } from '../lib/format'

const PRIORITY_CLASS: Record<PromptRow['priority'], string> = {
  Gold: 'bg-amber-50 text-amber-700 border border-amber-200',
  Silver: 'bg-gray-100 text-gray-700 border border-gray-200',
  Bronze: 'bg-orange-50 text-orange-600 border border-orange-200',
}

export function PriorityBadge({ priority }: { priority: PromptRow['priority'] }) {
  return <span className={`inline-flex rounded-md px-1.5 py-0.5 text-[11px] font-semibold ${PRIORITY_CLASS[priority] ?? PRIORITY_CLASS.Bronze}`}>{priority}</span>
}

export function MomentChip({ title }: { title: string }) {
  return <span className="inline-flex rounded-md px-1.5 py-0.5 text-[11px] font-medium bg-orange-100 text-orange-600">Moment: {title}</span>
}

type FilterKey = 'all' | 'missed' | 'bad' | 'moment'
const FILTERS: { key: FilterKey; label: string; test: (r: PromptRow) => boolean }[] = [
  { key: 'all', label: 'All', test: () => true },
  { key: 'missed', label: 'Missed (0/4)', test: r => r.engines_answered > 0 && r.engines_naming === 0 },
  { key: 'bad', label: 'Wrong or outdated', test: r => r.wrong_claims + r.outdated_claims > 0 },
  { key: 'moment', label: 'Moment-driven', test: r => r.moment_id !== null },
]

export default function PromptTable({ rows }: { rows: PromptRow[] }) {
  const navigate = useNavigate()
  const [filter, setFilter] = useState<FilterKey>('all')
  const test = FILTERS.find(f => f.key === filter)?.test ?? (() => true)
  const visible = rows.filter(test)

  return (
    <div className="card overflow-hidden">
      <div className="flex items-center justify-between flex-wrap gap-3 p-6 pb-4">
        <div className="flex items-center gap-3">
          <div className="icon-tile"><ListChecks className="w-5 h-5" /></div>
          <div>
            <h3 className="font-semibold">Tracked prompts</h3>
            <p className="text-sm text-text-secondary">{rows.length} tracked prompts, Gold first</p>
          </div>
        </div>
        <div className="flex flex-wrap gap-1 bg-surface-secondary rounded-2xl p-1.5">
          {FILTERS.map(f => (
            <button key={f.key} type="button" onClick={() => setFilter(f.key)} className={`nav-item !py-1.5 ${filter === f.key ? 'active' : ''}`}>
              {f.label}
            </button>
          ))}
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-y border-gray-100 bg-surface-secondary text-text-secondary">
              <th className="text-left font-medium px-6 py-2.5">Prompt</th>
              <th className="text-left font-medium px-3 py-2.5">Priority</th>
              <th className="text-right font-medium px-3 py-2.5 whitespace-nowrap">Engines naming LCE</th>
              <th className="text-right font-medium px-3 py-2.5 whitespace-nowrap">Our page cited</th>
              <th className="text-left font-medium px-3 py-2.5 whitespace-nowrap">Claim flags</th>
              <th className="text-right font-medium px-6 py-2.5 whitespace-nowrap">Est. monthly searches</th>
            </tr>
          </thead>
          <tbody>
            {visible.map(r => (
              <tr key={r.prompt_id} tabIndex={0} className="border-b border-gray-100 cursor-pointer hover:bg-gray-50"
                onClick={() => navigate(`/measure/prompts/${r.prompt_id}`)}
                onKeyDown={e => { if (e.key === 'Enter') navigate(`/measure/prompts/${r.prompt_id}`) }}>
                <td className="px-6 py-3">
                  <p className="font-medium">{r.prompt_text}</p>
                  {r.moment_title && <div className="mt-1"><MomentChip title={r.moment_title} /></div>}
                </td>
                <td className="px-3 py-3"><PriorityBadge priority={r.priority} /></td>
                <td className={`px-3 py-3 text-right tabular-nums ${r.engines_answered > 0 && r.engines_naming === 0 ? 'text-red-600 font-semibold' : ''}`}>{r.engines_naming}/4</td>
                <td className="px-3 py-3 text-right tabular-nums">{r.engines_owned_cited}/4</td>
                <td className="px-3 py-3">
                  <div className="flex flex-wrap gap-1">
                    {r.wrong_claims > 0 && <span className="rounded-md px-1.5 py-0.5 text-[11px] font-medium bg-red-50 text-red-700">{r.wrong_claims} wrong</span>}
                    {r.outdated_claims > 0 && <span className="rounded-md px-1.5 py-0.5 text-[11px] font-medium bg-amber-50 text-amber-700">{r.outdated_claims} outdated</span>}
                  </div>
                </td>
                <td className="px-6 py-3 text-right tabular-nums">{r.est_monthly_searches != null ? formatK(r.est_monthly_searches) : 'N/A'}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {visible.length === 0 && <p className="text-sm text-text-tertiary py-8 text-center">No tracked prompts match this filter.</p>}
      </div>
    </div>
  )
}
