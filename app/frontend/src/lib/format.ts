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
  // A bare date is a calendar day: parse it as local midnight so it never shifts a day in US time zones.
  const dt = new Date(/^\d{4}-\d{2}-\d{2}$/.test(d) ? `${d}T00:00:00` : d)
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

/** Engines in the order every screen lists them; unknown engines sort last. */
export const ENGINE_ORDER = ['Claude', 'ChatGPT', 'Gemini', 'Meta AI']
export function engineRank(engine: string): number {
  const i = ENGINE_ORDER.indexOf(engine)
  return i === -1 ? ENGINE_ORDER.length : i
}
