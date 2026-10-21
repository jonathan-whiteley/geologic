import { useMemo } from 'react'
import { TrendingUp } from 'lucide-react'
import { CartesianGrid, ComposedChart, Line, ReferenceDot, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { ImpactT } from '../api/types'
import { useTheme } from '../theme/ThemeContext'

const isLce = (b: string) => b.toLowerCase().includes('caesar')
const isDominos = (b: string) => b.toLowerCase().includes('domino')

function weekLabel(week: string) {
  const d = new Date(`${week.slice(0, 10)}T00:00:00`)
  return Number.isNaN(d.getTime()) ? week : d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

type Pt = { week: string; label: string; lce: number | null; dominos: number | null; approvals: string[] }

export default function ShareTrend({ weekly, markers }: Pick<ImpactT, 'weekly' | 'markers'>) {
  const { chart } = useTheme()
  const data = useMemo<Pt[]>(() => {
    const weeks = [...new Set(weekly.map(w => w.week_start.slice(0, 10)))].sort()
    return weeks.map(week => ({
      week,
      label: weekLabel(week),
      lce: weekly.find(w => w.week_start.startsWith(week) && isLce(w.brand))?.answer_share ?? null,
      dominos: weekly.find(w => w.week_start.startsWith(week) && isDominos(w.brand))?.answer_share ?? null,
      approvals: markers.filter(m => m.week_start.startsWith(week)).map(m => m.title),
    }))
  }, [weekly, markers])

  const dots = markers
    .map(m => ({ m, pt: data.find(p => m.week_start.startsWith(p.week)) }))
    .filter((x): x is { m: (typeof markers)[number]; pt: Pt } => !!x.pt && x.pt.lce != null)

  return (
    <div className="card p-6">
      <div className="flex items-center gap-3 mb-4">
        <div className="icon-tile"><TrendingUp className="w-5 h-5" /></div>
        <div>
          <h3 className="font-semibold">Little Caesars vs. Domino&apos;s</h3>
          <p className="text-sm text-text-secondary">Share of Model by week, with a dot on each approval</p>
        </div>
      </div>
      <div className="h-[260px]">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
            <CartesianGrid stroke={chart.gridColor} vertical={false} />
            <XAxis dataKey="label" tick={{ fontSize: 11, fill: chart.tickColor }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fontSize: 11, fill: chart.tickColor }} axisLine={false} tickLine={false} tickFormatter={(v: number) => v.toFixed(2)} width={40} />
            <Tooltip content={({ active, payload }) => {
              if (!active || !payload?.length) return null
              const p = payload[0].payload as Pt
              return (
                <div className="custom-tooltip text-sm space-y-1">
                  <p className="text-text-secondary text-xs">Week of {p.label}</p>
                  <p className="font-medium">Little Caesars: {p.lce != null ? p.lce.toFixed(2) : 'N/A'}</p>
                  <p className="font-medium">Domino&apos;s: {p.dominos != null ? p.dominos.toFixed(2) : 'N/A'}</p>
                  {p.approvals.map(t => <p key={t} className="text-xs text-lce-orange-dark">Approved: {t}</p>)}
                </div>
              )
            }} />
            <Line type="monotone" dataKey="dominos" stroke={chart.rival} strokeWidth={2} strokeDasharray="5 4" dot={false} isAnimationActive={false} />
            <Line type="monotone" dataKey="lce" stroke={chart.orange} strokeWidth={3} dot={false} isAnimationActive={false} />
            {dots.map(({ m, pt }) => (
              <ReferenceDot key={`${m.fix_id}-${m.approved_at}`} x={pt.label} y={pt.lce as number} r={6}
                fill={m.rehearsal ? 'none' : chart.orange} stroke={chart.orange} strokeWidth={2} />
            ))}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <div className="flex flex-wrap gap-5 text-xs text-text-secondary mt-2">
        <span className="flex items-center gap-2"><i className="w-4 h-1 rounded bg-lce-orange block" />Little Caesars</span>
        <span className="flex items-center gap-2"><i className="w-4 h-1 rounded bg-gray-300 block" />Domino&apos;s</span>
        <span className="flex items-center gap-2"><i className="w-2.5 h-2.5 rounded-full bg-lce-orange block" />Approval</span>
        <span className="flex items-center gap-2"><i className="w-2.5 h-2.5 rounded-full border-2 border-lce-orange block" />Rehearsal</span>
      </div>
    </div>
  )
}
