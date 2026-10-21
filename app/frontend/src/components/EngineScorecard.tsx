import type { AnswerT } from '../api/types'
import { engineRank } from '../lib/format'
import ClaimChip from './ClaimChip'
import CitationChip from './CitationChip'

/** One column per engine (display order): named or not, owned citation or not, citation chips and claim chips. */
export default function EngineScorecard({ answers }: { answers: AnswerT[] }) {
  const sorted = [...answers].sort((a, b) => engineRank(a.engine) - engineRank(b.engine))
  if (sorted.length === 0) return <p className="text-sm text-text-tertiary">No answers yet.</p>
  return (
    <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
      {sorted.map(a => {
        const ownedCited = a.cited.some(c => c.owner_class === 'Owned')
        const failed = a.status !== 'ok'
        return (
          <div key={a.engine} className="rounded-xl border border-gray-100 bg-surface-secondary p-3 space-y-2">
            <p className="text-sm font-semibold">{a.engine}</p>
            {failed ? (
              <p className="text-xs text-text-tertiary">No answer ({a.status})</p>
            ) : (
              <>
                <div className="flex flex-col gap-1 text-xs font-medium">
                  {a.lce_mentioned
                    ? <span className="text-green-700">{a.lce_rank ? `Named #${a.lce_rank}` : 'Named'}</span>
                    : <span className="text-red-700">Not named</span>}
                  {ownedCited
                    ? <span className="text-green-700">Our page cited</span>
                    : <span className="text-text-tertiary">No owned citation</span>}
                </div>
                {a.cited.length > 0 && (
                  <div className="flex flex-wrap gap-1">{a.cited.map(c => <CitationChip key={c.doc_id} doc={c} />)}</div>
                )}
                {a.claims.length > 0 && (
                  <div className="flex flex-wrap gap-1">{a.claims.map(c => <ClaimChip key={c.claim_id} claim={c} />)}</div>
                )}
              </>
            )}
          </div>
        )
      })}
    </div>
  )
}
