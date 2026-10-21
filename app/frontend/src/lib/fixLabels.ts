import type { IssueType } from '../api/types'

export const LANE_LABEL: Record<string, string> = {
  fix_page: 'Fix our page',
  request_correction: 'Request a correction',
  reply_as_brand: 'Reply as the brand',
  counter_content: 'Counter with our own content',
  publish_fact: 'Publish the right fact',
  capture_moment: 'Capture the moment',
}
export const laneLabel = (lane: string) => LANE_LABEL[lane] ?? lane.replace(/_/g, ' ')

export const ISSUE_TYPE: Record<IssueType, { label: string; cls: string }> = {
  wrong: { label: 'Wrong', cls: 'bg-red-50 text-red-700' },
  outdated: { label: 'Outdated', cls: 'bg-amber-50 text-amber-700' },
  missing_us: { label: 'Missing us', cls: 'bg-blue-50 text-blue-700' },
  no_answer_page: { label: 'No answer page', cls: 'bg-gray-100 text-gray-700' },
  moment_gap: { label: 'Moment gap', cls: 'bg-orange-100 text-orange-600' },
}

export const ASSET_LABEL: Record<string, string> = {
  jsonld: 'JSON-LD',
  owned_patch: 'Page patch',
  answer_page: 'Answer page',
  moment_page: 'Moment page',
  association: 'Association',
  correction_email: 'Correction email',
  community_reply: 'Community reply',
}
export const assetLabel = (a: string) => ASSET_LABEL[a] ?? a.replace(/_/g, ' ')

/** Message-style assets go to a named recipient instead of a page. */
export const MESSAGE_ASSETS = new Set(['correction_email', 'community_reply'])

/** Check keys that must pass before Approve is enabled. */
export const BLOCKING_CHECKS = new Set(['grounded', 'current', 'values', 'comparison', 'persona', 'copy', 'target', 'unsupported', 'policy', 'schema'])

export const TIER_ORDER: Record<string, number> = { T0: 0, T1: 1, T2: 2 }

export function tierClass(tier: string): string {
  return tier === 'T0' ? 't0' : tier === 'T1' ? 't1' : 't2'
}
