import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { NavLink } from 'react-router-dom'
import { Database, ShieldCheck, Sparkles } from 'lucide-react'
import {
  ComposedChart, Area, Line, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, ResponsiveContainer,
} from 'recharts'
import { api } from '../api/client'
import { PageSkeleton, ErrorRetry } from '../components/PageState'
import { STARTERS } from '../components/genie/GeniePanel'
import { useGeniePanel } from '../state/genie-panel'

const FIRST_PUBLISH_AFTER = '2026-09-14'

function isLce(brand: string) {
  return brand.toLowerCase().includes('caesar')
}
function isDominos(brand: string) {
  return brand.toLowerCase().includes('domino')
}

function weekLabel(week: string) {
  const d = new Date(week)
  if (Number.isNaN(d.getTime())) return week
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

export default function ProvePage() {
  const { data, isLoading, isError, refetch } = useQuery({ queryKey: ['impact'], queryFn: api.impact })
  const { ask, openPanel } = useGeniePanel()

  const chartData = useMemo(() => {
    if (!data) return []
    const weeks = [...new Set(data.weekly.map(w => w.week_start))].sort()
    return weeks.map(week => {
      const lce = data.weekly.find(w => w.week_start === week && isLce(w.brand))
      const dominos = data.weekly.find(w => w.week_start === week && isDominos(w.brand))
      return {
        week,
        label: weekLabel(week),
        lce: lce?.answer_share ?? null,
        dominos: dominos?.answer_share ?? null,
      }
    })
  }, [data])

  const firstPublishWeek = chartData.find(d => d.week > FIRST_PUBLISH_AFTER)

  if (isLoading) return <PageSkeleton statCards={0} />
  if (isError || !data) return <ErrorRetry message="Couldn't load Prove." onRetry={() => refetch()} />

  const { health } = data
  const p = data.proof

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <p className="text-xs font-semibold uppercase tracking-wider text-lce-orange-dark mb-1">Prove</p>
        <h2 className="text-2xl font-semibold">Did it work?</h2>
        <p className="text-text-secondary">What published fixes did to Share of Model, and what to ask next</p>
      </div>

      {p ? (
        <div className="card p-6 space-y-4">
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-green-700">Latest published fix</p>
              <h3 className="font-semibold text-lg">{p.title}</h3>
            </div>
            <div className="flex gap-6 text-sm">
              {p.share_before != null && p.share_after != null && <span>Share of Model <b className="tabular-nums">{p.share_before.toFixed(2)} → {p.share_after.toFixed(2)}</b></span>}
              {p.accuracy_before != null && p.accuracy_after != null && <span>Fact accuracy <b className="tabular-nums">{p.accuracy_before.toFixed(0)}% → {p.accuracy_after.toFixed(0)}%</b></span>}
            </div>
          </div>
          <div className="grid md:grid-cols-2 gap-4">
            <div className="rounded-xl border border-gray-100 p-4 space-y-2"><span className="badge b-default">Before · {p.engine}</span><p className="text-sm">{p.before_answer}</p></div>
            <div className="rounded-xl border border-green-100 p-4 space-y-2 shadow-soft"><span className="badge b-success"><span className="dot" />After · {p.engine}</span><p className="text-sm">{p.after_answer}</p>
              {p.after_cited.length > 0 && <p className="font-mono text-[11px] text-lce-orange-dark">cites: {p.after_cited.join(' · ')}</p>}</div>
          </div>
          <p className="text-xs text-text-tertiary flex items-center gap-1.5"><Database className="w-3.5 h-3.5" />Approved by {p.reviewer ?? 'presenter'} · {new Date(p.saved_at).toLocaleString()} · stored in Lakebase</p>
        </div>
      ) : (
        <div className="card p-6 text-sm text-text-tertiary">
          No published fix yet. Approve one in <NavLink to="/fix" className="text-lce-orange-dark font-medium hover:underline">Fix</NavLink>.
        </div>
      )}

      <div className="grid lg:grid-cols-3 gap-6">
        <div className="card p-6 lg:col-span-2">
          <div className="flex items-center gap-3 mb-4">
            <div className="icon-tile"><Sparkles className="w-5 h-5" /></div>
            <div>
              <h3 className="font-semibold">Share of Model, weekly</h3>
              <p className="text-sm text-text-secondary">Little Caesars vs. Domino&apos;s · dashed line marks first publish</p>
            </div>
          </div>
          <div className="h-[260px]">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="impactGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#FF671B" stopOpacity={0.25} />
                    <stop offset="100%" stopColor="#FF671B" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="#F0F1F2" vertical={false} />
                <XAxis dataKey="label" tick={{ fontSize: 11, fill: '#9CA3AF' }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: '#9CA3AF' }} axisLine={false} tickLine={false} tickFormatter={(v: number) => v.toFixed(2)} width={40} />
                <Tooltip
                  content={({ active, payload, label }) => {
                    if (!active || !payload?.length) return null
                    return (
                      <div className="custom-tooltip text-sm space-y-1">
                        <p className="text-text-secondary text-xs">{label}</p>
                        {payload.map(p => (
                          <p key={p.dataKey as string} className="font-medium flex items-center gap-2">
                            <span className="w-2 h-2 rounded-full" style={{ background: p.color }} />
                            {p.dataKey === 'lce' ? 'Little Caesars' : "Domino's"}: {typeof p.value === 'number' ? p.value.toFixed(2) : 'N/A'}
                          </p>
                        ))}
                      </div>
                    )
                  }}
                />
                {firstPublishWeek && (
                  <ReferenceLine x={firstPublishWeek.label} stroke="#1A1A1A" strokeOpacity={0.35} strokeDasharray="3 3"
                    label={{ value: 'First publish', position: 'insideTopLeft', fontSize: 11, fill: '#1A1A1A' }} />
                )}
                <Area type="monotone" dataKey="lce" stroke="none" fill="url(#impactGradient)" isAnimationActive={false} />
                <Line type="monotone" dataKey="dominos" stroke="#D1D5DB" strokeWidth={2} strokeDasharray="5 4" dot={false} isAnimationActive={false} />
                <Line type="monotone" dataKey="lce" stroke="#FF671B" strokeWidth={3} dot={false} isAnimationActive={false} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
          <div className="flex gap-5 text-xs text-text-secondary mt-2">
            <span className="flex items-center gap-2"><i className="w-4 h-1 rounded bg-lce-orange block" />Little Caesars</span>
            <span className="flex items-center gap-2"><i className="w-4 h-1 rounded bg-gray-300 block" />Domino&apos;s</span>
          </div>
        </div>

        <div className="card p-6 flex flex-col">
          <div className="flex items-center gap-3 mb-4">
            <div className="icon-tile"><Sparkles className="w-5 h-5" /></div>
            <div>
              <h3 className="font-semibold">What to ask next</h3>
              <p className="text-sm text-text-secondary">Genie answers with SQL on governed metric views</p>
            </div>
          </div>
          <div className="space-y-2 flex-1">
            {STARTERS.map(q => (
              <button key={q} type="button" className="btn btn-ghost w-full !justify-start text-left" onClick={() => ask(q)}>{q}</button>
            ))}
          </div>
          <button type="button" className="mt-4 text-sm font-medium text-lce-orange-dark hover:underline self-start" onClick={openPanel}>Open Ask Genie</button>
        </div>
      </div>

      <div className="card px-6 py-3 flex flex-wrap items-center gap-x-6 gap-y-2 text-xs">
        <span className="font-semibold flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-lce-orange" />
          Autonomy, last 30 days
        </span>
        <span><b className="tabular-nums">{health.t0_auto}</b> <span className="text-text-secondary">auto-published</span></span>
        <span>
          <b className="tabular-nums">{health.t1_approved_no_edit_pct !== null ? `${health.t1_approved_no_edit_pct.toFixed(0)}%` : 'n/a'}</b>{' '}
          <span className="text-text-secondary">approved without edits</span>
        </span>
        <span><b className="tabular-nums">{health.t2_reviews}</b> <span className="text-text-secondary">reviewed by a person</span></span>
        <span><b className="tabular-nums text-red-600">{health.blocked}</b> <span className="text-text-secondary">blocked by brand rules</span></span>
      </div>
    </div>
  )
}
