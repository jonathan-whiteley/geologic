import { Link } from 'react-router-dom'
import type { LedgerEntry } from '../api/types'
import { TagChip } from './ClaimChip'

/** Before → after per target prompt for one fix's re-ask. */
export default function LedgerMini({ entry, label, note }: { entry: LedgerEntry; label?: string; note?: string }) {
  const total = entry.engines_total || 4
  return (
    <div className="rounded-xl border border-green-100 bg-green-50 p-4 space-y-3">
      {label && <p className="text-xs font-semibold uppercase tracking-wider text-text-secondary">{label}</p>}
      {entry.prompts.map(p => (
        <div key={p.prompt_id} className="space-y-1">
          {p.prompt_text && <p className="text-sm font-medium">{p.prompt_text}</p>}
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
            <span>Our page cited <b className="tabular-nums">{p.before.owned_cited}/{total} → {p.after.owned_cited}/{total}</b></span>
            {(p.before.tag || p.after.tag) && (
              <span className="flex items-center gap-1.5"><TagChip tag={p.before.tag} /> → <TagChip tag={p.after.tag} /></span>
            )}
          </div>
        </div>
      ))}
      {entry.engines_answered < entry.engines_total && (
        <p className="text-xs text-amber-700">{entry.engines_answered} of {entry.engines_total} engines answered</p>
      )}
      {note && <p className="text-xs text-text-secondary">{note}</p>}
      <Link to="/impact" className="inline-block text-sm font-medium text-lce-orange-dark hover:underline">See it in Impact</Link>
    </div>
  )
}
