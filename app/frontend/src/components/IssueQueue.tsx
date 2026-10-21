import type { IssueRow, IssueType } from '../api/types'
import { ISSUE_TYPE, laneLabel, tierClass } from '../lib/fixLabels'

export type QueueFilter = 'all' | 'bad' | 'missing' | 'no_page' | 'moments'
const FILTERS: { key: QueueFilter; label: string; types: IssueType[] }[] = [
  { key: 'all', label: 'All', types: [] },
  { key: 'bad', label: 'Wrong or outdated', types: ['wrong', 'outdated'] },
  { key: 'missing', label: 'Missing us', types: ['missing_us'] },
  { key: 'no_page', label: 'No answer page', types: ['no_answer_page'] },
  { key: 'moments', label: 'Moments', types: ['moment_gap'] },
]

export function filterIssues(rows: IssueRow[], f: QueueFilter): IssueRow[] {
  const types = FILTERS.find(x => x.key === f)?.types ?? []
  return types.length ? rows.filter(r => types.includes(r.issue_type)) : rows
}

type Props = {
  rows: IssueRow[]; filter: QueueFilter; onFilter: (f: QueueFilter) => void; selectedId: string | undefined; onSelect: (id: string) => void
  clusterLabel: string | null; onClearCluster: () => void
}

export default function IssueQueue({ rows, filter, onFilter, selectedId, onSelect, clusterLabel, onClearCluster }: Props) {
  const visible = filterIssues(rows, filter)
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex flex-wrap gap-1 bg-surface-secondary rounded-2xl p-1.5">
          {FILTERS.map(f => (
            <button key={f.key} type="button" onClick={() => onFilter(f.key)} className={`nav-item !py-1.5 !px-3 ${filter === f.key ? 'active' : ''}`}>{f.label}</button>
          ))}
        </div>
        {clusterLabel && (
          <button type="button" onClick={onClearCluster} title="Remove the cluster filter"
            className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium bg-orange-50 text-orange-600 border border-orange-200 hover:bg-orange-100">
            Cluster: {clusterLabel} <span aria-hidden>×</span>
          </button>
        )}
      </div>

      <div className="card p-2 space-y-1">
        {visible.map(r => {
          const t = ISSUE_TYPE[r.issue_type]
          const sel = r.issue_id === selectedId
          const n = r.prompt_ids.length
          return (
            <button key={r.issue_id} type="button" onClick={() => onSelect(r.issue_id)}
              className={`w-full text-left p-3 rounded-xl flex gap-3 items-start transition-colors ${sel ? 'ring-1 ring-lce-orange/30 bg-lce-orange/5' : 'hover:bg-gray-50'}`}>
              <div className={`w-8 h-8 shrink-0 rounded-lg flex items-center justify-center text-sm font-semibold ${r.rank === 1 ? 'lce-gradient text-white shadow-glow-orange' : 'bg-surface-tertiary text-text-secondary'}`}>{r.rank}</div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium line-clamp-2">{r.title}</p>
                <div className="flex flex-wrap items-center gap-x-2 gap-y-1 mt-1.5 text-xs">
                  {t && <span className={`rounded-md px-1.5 py-0.5 font-medium ${t.cls}`}>{t.label}</span>}
                  <span className="text-text-secondary">{laneLabel(r.action_lane)}</span>
                </div>
                <div className="flex flex-wrap items-center gap-x-2 gap-y-1 mt-1 text-xs text-text-tertiary">
                  <span>on {n} tracked {n === 1 ? 'prompt' : 'prompts'} · {r.missed_answers} missed answers</span>
                  {r.fixes.map(f => <span key={f.fix_id} className={`tier ${tierClass(f.tier)}`}>{f.tier}</span>)}
                </div>
              </div>
            </button>
          )
        })}
        {visible.length === 0 && <p className="text-sm text-text-tertiary py-8 text-center">No issues in this filter.</p>}
      </div>
    </div>
  )
}
