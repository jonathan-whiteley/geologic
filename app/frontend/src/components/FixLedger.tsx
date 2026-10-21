import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ChevronDown, Database, ScrollText } from 'lucide-react'
import type { LedgerEntry } from '../api/types'
import { cleanAnswer, engineRank, formatTime } from '../lib/format'
import { tierClass } from '../lib/fixLabels'
import { TagChip } from './ClaimChip'

function DocChips({ ids }: { ids: string[] }) {
  if (ids.length === 0) return <span className="text-[11px] text-text-tertiary">no citations</span>
  return (
    <>
      {ids.map(id => (
        <span key={id} className={`font-mono text-[11px] px-1.5 py-0.5 rounded-md ${id.startsWith('lce_') ? 'bg-orange-50 text-lce-orange-dark' : 'bg-gray-100 text-gray-700'}`}>{id}</span>
      ))}
    </>
  )
}

function Row({ e }: { e: LedgerEntry }) {
  const [open, setOpen] = useState(false)
  const total = e.engines_total || 4
  const when = e.approved_at ?? e.measured_at
  return (
    <div className={`py-4 space-y-2 ${e.rehearsal ? 'opacity-60' : ''}`}>
      <button type="button" className="w-full text-left flex items-start gap-3" aria-expanded={open} onClick={() => setOpen(v => !v)}>
        <span className={`tier ${tierClass(e.tier)} mt-0.5`}>{e.tier}</span>
        <div className="flex-1 min-w-0 space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="font-medium">{e.title}</p>
            {e.rehearsal && <span className="badge b-default">Rehearsal · {formatTime(when)}</span>}
          </div>
          <p className="text-xs text-text-tertiary">
            {e.reviewer ?? 'presenter'} · {new Date(when).toLocaleString()}
            {e.elapsed_s != null && <> · {Math.round(e.elapsed_s)}s to proof</>}
            {e.engines_answered < e.engines_total && <span className="text-amber-700"> · {e.engines_answered} of {e.engines_total} engines answered</span>}
          </p>
          {e.prompts.map(p => (
            <div key={p.prompt_id} className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
              {p.prompt_text && <span className="text-text-secondary w-full">{p.prompt_text}</span>}
              <span>Mentioned <b className="tabular-nums">{p.before.mentioned}/{total} → {p.after.mentioned}/{total}</b></span>
              <span>Our page cited <b className="tabular-nums">{p.before.owned_cited}/{total} → {p.after.owned_cited}/{total}</b></span>
              {(p.before.tag || p.after.tag) && <span className="flex items-center gap-1.5"><TagChip tag={p.before.tag} /> → <TagChip tag={p.after.tag} /></span>}
            </div>
          ))}
        </div>
        <ChevronDown className={`w-4 h-4 text-text-secondary mt-1 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && e.prompts.map(p => (
        <div key={p.prompt_id} className="space-y-3 pl-9">
          {[...p.answers].sort((a, b) => engineRank(a.engine) - engineRank(b.engine)).map(a => (
            <div key={a.engine} className="grid md:grid-cols-2 gap-3">
              <div className="rounded-xl border border-gray-100 p-3 space-y-1.5">
                <span className="badge b-default">Before · {a.engine}</span>
                <p className="text-sm">{a.before_answer ? cleanAnswer(a.before_answer) : <span className="text-text-tertiary">No answer captured</span>}</p>
                <div className="flex flex-wrap gap-1"><DocChips ids={a.before_cited} /></div>
              </div>
              <div className="rounded-xl border border-green-100 p-3 space-y-1.5">
                <span className="badge b-success">After · {a.engine}</span>
                <p className="text-sm">{a.after_answer ? cleanAnswer(a.after_answer) : <span className="text-text-tertiary">{a.status !== 'ok' ? `No answer (${a.status})` : 'No answer captured'}</span>}</p>
                <div className="flex flex-wrap gap-1"><DocChips ids={a.after_cited} /></div>
              </div>
            </div>
          ))}
        </div>
      ))}
    </div>
  )
}

export default function FixLedger({ ledger }: { ledger: LedgerEntry[] }) {
  return (
    <div className="card p-6">
      <div className="flex items-center gap-3">
        <div className="icon-tile"><ScrollText className="w-5 h-5" /></div>
        <div>
          <h3 className="font-semibold">Fix ledger</h3>
          <p className="text-sm text-text-secondary">Every approved fix, with the engines&apos; answer before and after</p>
        </div>
      </div>
      {ledger.length === 0 ? (
        <p className="text-sm text-text-tertiary py-6">
          No fixes approved yet. Approve one in <Link to="/fix" className="text-lce-orange-dark font-medium hover:underline">Fix</Link>.
        </p>
      ) : (
        <div className="divide-y divide-gray-100">{ledger.map(e => <Row key={`${e.fix_id}-${e.measured_at}`} e={e} />)}</div>
      )}
      <p className="text-xs text-text-tertiary flex items-center gap-1.5 mt-2"><Database className="w-3.5 h-3.5" />Stored in Lakebase</p>
    </div>
  )
}
