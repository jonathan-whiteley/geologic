import { useNavigate } from 'react-router-dom'
import type { ClaimT, Tag } from '../api/types'

export const TAG_CLASS: Record<Tag, string> = {
  Correct: 'bg-green-50 text-green-700',
  Wrong: 'bg-red-50 text-red-700',
  Outdated: 'bg-amber-50 text-amber-700',
  Unverifiable: 'bg-gray-100 text-gray-700',
}

export function TagChip({ tag }: { tag: Tag | null }) {
  if (!tag) return <span className="text-xs text-text-tertiary">no claim</span>
  return <span className={`inline-flex rounded-md px-1.5 py-0.5 text-[11px] font-medium ${TAG_CLASS[tag]}`}>{tag}</span>
}

/** A tagged claim: `{stated_value} · {tag}`; opens its issue in Fix when it has one. */
export default function ClaimChip({ claim }: { claim: Pick<ClaimT, 'stated_value' | 'tag' | 'issue_id' | 'text'> }) {
  const navigate = useNavigate()
  const label = `${claim.stated_value ?? 'claim'} · ${claim.tag}`
  const cls = `inline-flex items-center rounded-md px-2 py-0.5 text-[11px] font-medium ${TAG_CLASS[claim.tag] ?? TAG_CLASS.Unverifiable}`
  if (claim.issue_id) {
    return (
      <button type="button" className={`${cls} hover:ring-1 hover:ring-current`} title="Open the issue in Fix"
        onClick={e => { e.stopPropagation(); navigate(`/fix?issue=${encodeURIComponent(claim.issue_id as string)}`) }}>
        {label}
      </button>
    )
  }
  return <span className={cls} title={claim.text ?? undefined}>{label}</span>
}
