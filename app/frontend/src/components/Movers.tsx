import { Link } from 'react-router-dom'
import { ArrowDownRight, ArrowUpRight, Flame, Target } from 'lucide-react'
import type { ImpactT, Mover } from '../api/types'
import { CLUSTERS } from './Heatmap'

const CLUSTER_LABEL = new Map(CLUSTERS)

function MoverList({ title, rows, up }: { title: string; rows: Mover[]; up: boolean }) {
  const Icon = up ? ArrowUpRight : ArrowDownRight
  return (
    <div className="space-y-2">
      <p className={`text-sm font-semibold flex items-center gap-1.5 ${up ? 'text-green-700' : 'text-red-700'}`}><Icon className="w-4 h-4" />{title}</p>
      {rows.length === 0 ? <p className="text-xs text-text-tertiary">None yet.</p> : rows.map(m => (
        <Link key={m.prompt_id} to={`/measure/prompts/${m.prompt_id}`} className="flex items-center gap-3 text-sm hover:underline">
          <span className="flex-1 min-w-0 truncate">{m.prompt_text}</span>
          <span className="tabular-nums text-text-secondary whitespace-nowrap">{m.naming_before}/4 → {m.naming_after}/4</span>
        </Link>
      ))}
    </div>
  )
}

export default function Movers({ d }: { d: ImpactT }) {
  return (
    <div className="grid lg:grid-cols-3 gap-6">
      <div className="card p-6 space-y-5">
        <MoverList title="Biggest gains" rows={d.movers.gains} up />
        <MoverList title="Biggest drops" rows={d.movers.drops} up={false} />
      </div>
      <div className="card p-6 space-y-3">
        <p className="text-sm font-semibold flex items-center gap-1.5"><Target className="w-4 h-4 text-lce-orange" />Most missed answers by cluster</p>
        {d.missed_by_cluster.length === 0 ? <p className="text-xs text-text-tertiary">No missed answers.</p> : d.missed_by_cluster.map(c => (
          <Link key={c.cluster} to={`/fix?cluster=${encodeURIComponent(c.cluster)}`} className="flex items-center gap-3 text-sm hover:underline">
            <span className="flex-1">{CLUSTER_LABEL.get(c.cluster) ?? c.cluster}</span>
            <span className="tabular-nums font-semibold">{c.missed}</span>
          </Link>
        ))}
      </div>
      <div className="card p-6 space-y-3">
        <p className="text-sm font-semibold flex items-center gap-1.5"><Flame className="w-4 h-4 text-lce-orange" />Live moments not yet captured</p>
        {d.live_moments.length === 0 ? <p className="text-xs text-text-tertiary">Every live moment is captured.</p> : d.live_moments.map(m => (
          <div key={m.moment_id} className="space-y-0.5">
            <p className="text-sm">{m.title}</p>
            {m.issue_id
              ? <Link to={`/fix?issue=${encodeURIComponent(m.issue_id)}`} className="text-xs font-medium text-lce-orange-dark hover:underline">Open in Fix</Link>
              : <Link to="/measure" className="text-xs font-medium text-lce-orange-dark hover:underline">Track the prompt in Measure</Link>}
          </div>
        ))}
      </div>
    </div>
  )
}
