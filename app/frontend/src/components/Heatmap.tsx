import type { HeatCell } from '../api/types'

const CLUSTERS: [string, string][] = [
  ['product', 'Product questions'],
  ['value', 'Value and deals'],
  ['comparison', 'Comparisons'],
  ['ordering', 'Ordering / Pizza Portal'],
  ['dietary', 'Dietary'],
  ['game_day_party', 'Game-day / party sizing'],
  ['sponsorship', 'Sponsorship (NFL)'],
]

const ENGINES = ['Claude', 'ChatGPT', 'Gemini', 'Meta AI']

function hc(v: number): string {
  if (v >= 0.5) return 'bg-lce-orange-dark text-white'
  if (v >= 0.4) return 'bg-orange-400 text-white'
  if (v >= 0.3) return 'bg-orange-200'
  if (v >= 0.15) return 'bg-orange-100'
  return 'bg-orange-50'
}

interface HeatmapProps {
  data: HeatCell[]
  onCellClick?: (cluster: string) => void
}

export default function Heatmap({ data, onCellClick }: HeatmapProps) {
  const byKey = new Map(data.map(d => [`${d.cluster}::${d.engine}`, d.answer_share]))
  // Only clusters that have data: a cluster with no unbranded answers is left out rather than shown as 0.00.
  const present = new Set(data.map(d => d.cluster))
  const known = new Set(CLUSTERS.map(([k]) => k))
  const rows: [string, string][] = [
    ...CLUSTERS.filter(([k]) => present.has(k)),
    ...[...present].filter(k => !known.has(k)).map(k => [k, k] as [string, string]),
  ]

  return (
    <div>
      <table className="heat w-full border-separate border-spacing-1">
        <thead>
          <tr>
            <th></th>
            {ENGINES.map(e => (
              <th key={e} className="text-xs font-medium text-text-secondary text-center pb-1">{e}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map(([key, label]) => (
            <tr key={key}>
              <th className="text-sm font-medium text-left pr-3 whitespace-nowrap">{label}</th>
              {ENGINES.map(engine => {
                const v = byKey.get(`${key}::${engine}`)
                const has = typeof v === 'number' && Number.isFinite(v)
                return (
                  <td
                    key={engine}
                    tabIndex={0}
                    className={`cell ${has ? hc(v) : 'bg-gray-50 text-text-tertiary'}`}
                    onClick={() => onCellClick?.(key)}
                    onKeyDown={e => { if (e.key === 'Enter') onCellClick?.(key) }}
                  >
                    {has ? v.toFixed(2) : 'N/A'}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="flex items-center gap-1 text-xs text-text-tertiary mt-3">
        0.0
        <i className="w-6 h-2 rounded-sm bg-orange-50 block" />
        <i className="w-6 h-2 rounded-sm bg-orange-100 block" />
        <i className="w-6 h-2 rounded-sm bg-orange-200 block" />
        <i className="w-6 h-2 rounded-sm bg-orange-400 block" />
        <i className="w-6 h-2 rounded-sm bg-lce-orange-dark block" />
        0.5+
      </div>
    </div>
  )
}

export { CLUSTERS }
