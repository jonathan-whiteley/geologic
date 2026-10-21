import { Filter } from 'lucide-react'
import type { Funnel, Phase } from '../api/types'

const STAGES: { key: keyof Funnel; label: string }[] = [
  { key: 'answers', label: 'Answers' },
  { key: 'mention_lce', label: 'Mention LCE' },
  { key: 'cite_lce', label: 'Cite an LCE page' },
  { key: 'pick_lce_first', label: 'Pick LCE first' },
]

const pctOf = (n: number, d: number) => (d > 0 ? Math.round((n / d) * 100) : 0)

function Bar({ value, total, cls, label }: { value: number; total: number; cls: string; label: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="w-12 text-[11px] text-text-tertiary">{label}</span>
      <div className="flex-1 h-3 rounded-full bg-surface-tertiary overflow-hidden">
        <div className={`h-full rounded-full ${cls}`} style={{ width: `${pctOf(value, total)}%` }} />
      </div>
      <span className="w-20 text-right text-xs tabular-nums">{value} · {pctOf(value, total)}%</span>
    </div>
  )
}

export default function GeoFunnel({ funnel }: { funnel: Phase<Funnel> }) {
  return (
    <div className="card p-6 space-y-4">
      <div className="flex items-center gap-3">
        <div className="icon-tile"><Filter className="w-5 h-5" /></div>
        <div>
          <h3 className="font-semibold">Getting cited is what gets us picked</h3>
          <p className="text-sm text-text-secondary">Before and after, as a share of answers</p>
        </div>
      </div>
      <div className="space-y-4">
        {STAGES.map(s => (
          <div key={s.key} className="space-y-1">
            <p className="text-sm font-medium">{s.label}</p>
            <Bar label="Before" value={funnel.before[s.key]} total={funnel.before.answers} cls="bg-gray-300" />
            <Bar label="After" value={funnel.after[s.key]} total={funnel.after.answers} cls="bg-lce-orange" />
          </div>
        ))}
      </div>
    </div>
  )
}
