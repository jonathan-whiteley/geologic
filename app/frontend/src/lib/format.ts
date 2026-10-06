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
