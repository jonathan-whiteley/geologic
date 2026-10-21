import { Flame } from 'lucide-react'
import type { MomentT } from '../api/types'
import { formatK } from '../lib/format'

export default function MomentCard({ m }: { m: MomentT }) {
  return (
    <div className="rounded-xl border border-orange-200 bg-orange-50 p-4 flex gap-4 flex-wrap">
      {m.image_url && (
        <figure className="w-40 shrink-0">
          <img src={m.image_url} alt={m.title} className="w-40 h-28 object-cover rounded-lg border border-gray-100" />
          {m.image_credit && <figcaption className="text-[10px] text-text-tertiary mt-1">Photo: {m.image_credit}</figcaption>}
        </figure>
      )}
      <div className="min-w-0 flex-1 space-y-2">
        <p className="flex items-center gap-2 text-sm font-semibold"><Flame className="w-4 h-4 text-lce-orange" />{m.title}</p>
        <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
          {m.author && <><span className="text-text-tertiary">Author</span><span className="font-medium">{m.author}</span></>}
          {m.persona_name && <><span className="text-text-tertiary">Person</span><span className="font-medium">{m.persona_name}</span></>}
          {m.reach != null && <><span className="text-text-tertiary">Reach</span><span className="font-medium tabular-nums">{formatK(m.reach)}</span></>}
          {m.velocity != null && <><span className="text-text-tertiary">Velocity</span><span className="font-medium tabular-nums">{m.velocity}x</span></>}
          <span className="text-text-tertiary">Matched item</span><span className="font-medium">{m.item_name}</span>
          {m.image_match != null && <><span className="text-text-tertiary">Image match</span><span className="font-medium tabular-nums">{Math.round(m.image_match * 100)}%</span></>}
        </div>
      </div>
    </div>
  )
}
