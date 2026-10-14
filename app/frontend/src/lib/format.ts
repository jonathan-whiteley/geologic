export function formatK(n: number): string {
  if (n >= 1000) return `${Math.round(n / 1000)}K`
  return String(Math.round(n))
}

export function formatK1(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`
  return String(Math.round(n))
}

export function pct(n: number, digits = 0): string {
  return `${n.toFixed(digits)}%`
}

export function formatDate(d: string | null): string {
  if (!d) return 'never'
  const dt = new Date(d)
  if (Number.isNaN(dt.getTime())) return d
  return dt.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

export function formatTime(d: string | null): string {
  if (!d) return ''
  const dt = new Date(d)
  if (Number.isNaN(dt.getTime())) return d
  return dt.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })
}

/** Null-safe fixed-point: missing or non-finite values (for example mid-reset) render as N/A instead of throwing. */
export function fx(n: number | null | undefined, digits = 2, suffix = ''): string {
  return typeof n === 'number' && Number.isFinite(n) ? `${n.toFixed(digits)}${suffix}` : 'N/A'
}

/** Answer text for display: drop inline citation tokens like [comp_dominos_party_guide] or [blog_a, lce_pg_deals];
 *  the sources are listed under the answer instead. */
/** Engine answers arrive as light markdown with inline citation tokens: show them as plain sentences. */
export function cleanAnswer(text: string): string {
  return text
    .replace(/\s*\[[\w ,.-]+\]/g, '')               // [lce_pg_order], [a, b]
    .replace(/\*\*\s*(.+?)\s*\*\*/g, '$1')          // **bold**
    .replace(/__(.+?)__/g, '$1')                    // __bold__
    .replace(/(^|[\s(])\*(\S[^*\n]*?)\*(?=[\s).,;:!?]|$)/g, '$1$2') // *italic*
    .replace(/\*\*/g, '')                           // unpaired markers
    .replace(/^\s*[-*]\s+/gm, '')                   // list bullets
    .replace(/[ \t]{2,}/g, ' ')
    .replace(/\s+([.,;:!?])/g, '$1')
    .trim()
}

export type MetricMove = { share_before: number | null; share_after: number | null; accuracy_before: number | null; accuracy_after: number | null }

/** Only the metrics that moved (at display precision), Share of Model first: a flat metric is left out. */
export function movedMetrics(m: MetricMove): { label: string; before: string; after: string }[] {
  const out: { label: string; before: string; after: string }[] = []
  if (m.share_before != null && m.share_after != null && m.share_before.toFixed(2) !== m.share_after.toFixed(2)) {
    out.push({ label: 'Share of Model', before: m.share_before.toFixed(2), after: m.share_after.toFixed(2) })
  }
  if (m.accuracy_before != null && m.accuracy_after != null && m.accuracy_before.toFixed(0) !== m.accuracy_after.toFixed(0)) {
    out.push({ label: 'Fact accuracy', before: `${m.accuracy_before.toFixed(0)}%`, after: `${m.accuracy_after.toFixed(0)}%` })
  }
  return out
}

/** Engines in the order every screen lists them; unknown engines sort last. */
export const ENGINE_ORDER = ['Claude', 'ChatGPT', 'Gemini', 'Meta AI']
export function engineRank(engine: string): number {
  const i = ENGINE_ORDER.indexOf(engine)
  return i === -1 ? ENGINE_ORDER.length : i
}
