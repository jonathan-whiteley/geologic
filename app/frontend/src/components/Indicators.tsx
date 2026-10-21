import { ArrowDownRight, ArrowRight, ArrowUpRight, Gauge, Timer } from 'lucide-react'
import type { ImpactT } from '../api/types'
import { fx } from '../lib/format'
import CitationTracker from './CitationTracker'

type Better = 'up' | 'down'

function Move({ label, before, after, fmt, better }: { label: string; before: number | null; after: number | null; fmt: (n: number | null) => string; better: Better }) {
  const delta = before != null && after != null ? after - before : 0
  const flat = Math.abs(delta) < 1e-9
  const good = !flat && (better === 'up' ? delta > 0 : delta < 0)
  const cls = flat ? 'text-text-tertiary' : good ? 'text-green-700' : 'text-red-700'
  const Icon = flat ? ArrowRight : delta > 0 ? ArrowUpRight : ArrowDownRight
  return (
    <div className="flex items-center gap-3 py-2">
      <span className="flex-1 text-sm">{label}</span>
      <span className="tabular-nums text-sm text-text-secondary">{fmt(before)} → <b className="text-text-primary">{fmt(after)}</b></span>
      <Icon className={`w-4 h-4 ${cls}`} />
    </div>
  )
}

/** Visibility arrives as a 0 to 1 rate or an already scaled percent; show it as a percent either way. */
const asPct = (n: number | null) => (n == null ? null : n <= 1 ? n * 100 : n)
const int = (n: number | null) => (n == null ? 'N/A' : String(n))

export default function Indicators({ d }: { d: ImpactT }) {
  const { leading, lagging } = d
  return (
    <div className="grid lg:grid-cols-2 gap-6">
      <div className="card p-6 space-y-2">
        <div className="flex items-center gap-3 mb-2">
          <div className="icon-tile"><Gauge className="w-5 h-5" /></div>
          <h3 className="font-semibold">Leading: moves within one probe</h3>
        </div>
        <div className="divide-y divide-gray-100">
          <Move label="Our page retrieved" before={leading.before.owned_retrieved} after={leading.after.owned_retrieved} fmt={int} better="up" />
          <Move label="Our page cited" before={leading.before.cite_lce} after={leading.after.cite_lce} fmt={int} better="up" />
          <Move label="Wrong and outdated claims" before={leading.before.wrong_or_outdated} after={leading.after.wrong_or_outdated} fmt={int} better="down" />
        </div>
        <CitationTracker pages={d.patched_pages} />
      </div>
      <div className="card p-6 space-y-2 self-start">
        <div className="flex items-center gap-3 mb-2">
          <div className="icon-tile"><Timer className="w-5 h-5" /></div>
          <h3 className="font-semibold">Lagging: moves over weeks</h3>
        </div>
        <div className="divide-y divide-gray-100">
          <Move label="Share of Model" before={lagging.before.answer_share} after={lagging.after.answer_share} fmt={n => fx(n)} better="up" />
          <Move label="Visibility" before={asPct(lagging.before.mention_rate)} after={asPct(lagging.after.mention_rate)} fmt={n => fx(n, 0, '%')} better="up" />
          <Move label="Position" before={lagging.before.avg_rank} after={lagging.after.avg_rank} fmt={n => fx(n, 1)} better="down" />
        </div>
      </div>
    </div>
  )
}
