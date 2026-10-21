import type { SourceType } from '../api/types'
import { OWNER_ORDER, ownerClass } from '../lib/owners'
import { fx } from '../lib/format'

/** One stacked bar of citation share by owner class, in the fixed order, with a legend. */
export default function SourceTypeBar({ data }: { data: SourceType[] }) {
  const by = new Map(data.map(d => [d.owner_class, d]))
  const rows = OWNER_ORDER.map(k => by.get(k)).filter((d): d is SourceType => !!d && d.share > 0)
  return (
    <div className="space-y-3">
      <div className="flex h-4 rounded-full overflow-hidden bg-surface-tertiary">
        {rows.map(r => (
          <div key={r.owner_class} className={ownerClass(r.owner_class)} style={{ width: `${r.share}%` }}
            title={`${r.owner_class} ${fx(r.share, 0, '%')} · ${r.citations} citations`} />
        ))}
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-text-secondary">
        {rows.map(r => (
          <span key={r.owner_class} className="flex items-center gap-1.5">
            <i className={`w-2.5 h-2.5 rounded-sm block ${ownerClass(r.owner_class)}`} />
            {r.owner_class} {fx(r.share, 0, '%')}
          </span>
        ))}
      </div>
    </div>
  )
}
