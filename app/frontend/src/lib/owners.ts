import type { OwnerClass } from '../api/types'

/** Fixed display order for source owner classes. */
export const OWNER_ORDER: OwnerClass[] = ['Owned', 'Competitor', 'Editorial', 'Community', 'Reference']

const SOLID: Record<OwnerClass, string> = {
  Owned: 'bg-lce-orange text-white',
  Competitor: 'bg-gray-600 text-surface',
  Editorial: 'bg-blue-600 text-surface',
  Community: 'bg-amber-600 text-surface',
  Reference: 'bg-green-600 text-surface',
}

const CHIP: Record<OwnerClass, string> = {
  Owned: 'bg-orange-50 text-lce-orange-dark',
  Competitor: 'bg-gray-50 text-gray-700',
  Editorial: 'bg-blue-50 text-blue-700',
  Community: 'bg-amber-50 text-amber-700',
  Reference: 'bg-green-50 text-green-700',
}

/** Solid classes (bars, badges) for an owner class; unknown owners fall back to gray. */
export function ownerClass(owner: string): string {
  return SOLID[owner as OwnerClass] ?? 'bg-gray-600 text-surface'
}

/** Soft chip classes (-50 background, -700 text) for an owner class. */
export function ownerChip(owner: string): string {
  return CHIP[owner as OwnerClass] ?? 'bg-gray-50 text-gray-700'
}
