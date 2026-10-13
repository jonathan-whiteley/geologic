/** Formatting for Genie results: every value arrives as a string, so format by column name (GEOlogic rules). */

export type ColumnKind = 'currency' | 'percent' | 'integer' | 'decimal' | 'date' | 'text'

const PERCENT = new Set(['fact_accuracy', 'mention_rate', 'visibility', 'citation_rate', 'owned_citation_share', 'citation_share'])
const INTEGER = new Set(['est_volume', 'question_volume', 'avg_monthly_volume', 'answers', 'citations', 'wrong_claims'])
const INT_TYPES = ['INT', 'LONG', 'BIGINT', 'SHORT', 'TINYINT', 'SMALLINT']
const DECIMAL_TYPES = ['DOUBLE', 'FLOAT', 'DECIMAL']

/** "Share of Model", `share_of_model` and `Share-of-Model` all normalize to share_of_model. */
function normalize(name: string): string {
  return name.trim().toLowerCase().replace(/[\s-]+/g, '_')
}

export function columnKind(name: string, type = ''): ColumnKind {
  const n = normalize(name)
  const t = type.toUpperCase()
  if (/^(year|quarter|fiscal_year)$/.test(n) || t === 'BOOLEAN') return 'text'
  if (PERCENT.has(n) || /(_pct|_rate)$/.test(n)) return 'percent'
  // Share of Model is a 0 to 1 score: always a decimal, never a percent. Genie aliases it freely
  // (lce_share, dominos_share, brand_share), so any other *_share column is a decimal too.
  if (n === 'share' || /(answer_share|share_of_model)/.test(n) || /_share$/.test(n)) return 'decimal'
  if (INTEGER.has(n)) return 'integer'
  if (/(^|_)price($|_)/.test(n)) return 'currency'
  if (t === 'DATE' || t.startsWith('TIMESTAMP') || /(^|_)(date|week|month|week_start)($|_)/.test(n)) return 'date'
  if (/(^|_)(pct|percent)(_|$)/.test(n)) return 'percent'
  if (INT_TYPES.some(x => t.startsWith(x))) return 'integer'
  if (DECIMAL_TYPES.some(x => t.startsWith(x))) return 'decimal'
  return 'text'
}

export function isNumericKind(k: ColumnKind) {
  return k !== 'text' && k !== 'date'
}

export function formatValue(v: unknown, kind: ColumnKind): string {
  if (v === null || v === undefined || v === '') return ''
  const s = String(v)
  if (!isNumericKind(kind)) {
    if (s === 'true') return 'Yes'
    if (s === 'false') return 'No'
    if (kind === 'date' && /^\d{4}-\d{2}-\d{2}/.test(s)) return formatDate(s.slice(0, 10))
    return s
  }
  const x = Number(s)
  if (!Number.isFinite(x)) return s
  switch (kind) {
    case 'currency':
      return x.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: Math.abs(x) >= 100000 ? 0 : 2 })
    case 'percent':
      return `${(Math.abs(x) <= 1.5 ? x * 100 : x).toFixed(1)}%`
    case 'integer':
      return Math.round(x).toLocaleString('en-US')
    default:
      return Math.abs(x) >= 1000
        ? x.toLocaleString('en-US', { maximumFractionDigits: 0 })
        : x.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  }
}

/** Parse YYYY-MM-DD as a local calendar date (new Date('2026-10-04') would shift by timezone). */
function formatDate(s: string): string {
  const [y, m, d] = s.split('-').map(Number)
  return new Date(y, (m || 1) - 1, d || 1).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

const LABELS: Record<string, string> = {
  answer_share: 'Share of Model',
  share_of_model: 'Share of Model',
  mention_rate: 'Visibility',
  lce_rank: 'LCE rank',
}

export function prettyLabel(col: string): string {
  const special = LABELS[normalize(col)]
  if (special) return special
  return col.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()).replace(/\bLce\b/g, 'LCE').replace(/\bAnswer Share\b/g, 'Share of Model')
}

/** Display cleanup for Genie strings the backend does not clean (follow-up chips, errors): no em or en dashes on screen. */
export function noDashes(s: string): string {
  return s
    .replace(/\s+[\u2014\u2013]\s+/g, ', ')
    .replace(/\u2013/g, '-')
    .replace(/\u2014/g, ', ')
}
