import { useMemo, useState, type FormEvent } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ShieldCheck, Sparkles, Send } from 'lucide-react'
import {
  ComposedChart, Area, Line, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, ResponsiveContainer,
} from 'recharts'
import { api } from '../api/client'
import { PageSkeleton, ErrorRetry } from '../components/PageState'

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

interface ChatMsg { role: 'user' | 'assistant'; text: string }

export default function ImpactPage() {
  const { data, isLoading, isError, refetch } = useQuery({ queryKey: ['impact'], queryFn: api.impact })
  const [messages, setMessages] = useState<ChatMsg[]>([])
  const [question, setQuestion] = useState('')
  const [asking, setAsking] = useState(false)
  const [askError, setAskError] = useState<string | null>(null)

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
  if (isError || !data) return <ErrorRetry message="Couldn't load Impact." onRetry={() => refetch()} />

  async function handleAsk(e: FormEvent) {
    e.preventDefault()
    const q = question.trim()
    if (!q || asking) return
    setMessages(prev => [...prev, { role: 'user', text: q }])
    setQuestion('')
    setAsking(true)
    setAskError(null)
    try {
      const res = await api.ask(q)
      setMessages(prev => [...prev, { role: 'assistant', text: res.answer }])
    } catch (err) {
      setAskError(err instanceof Error ? err.message : 'Something went wrong.')
    } finally {
      setAsking(false)
    }
  }

  const { health } = data

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <p className="text-xs font-semibold uppercase tracking-wider text-lce-orange-dark mb-1">Impact</p>
        <h2 className="text-2xl font-semibold">Impact</h2>
        <p className="text-text-secondary">What published changes did to Answer Share, and how the autonomy guardrails are holding</p>
      </div>

      <div className="card px-6 py-4 flex flex-wrap items-center gap-x-8 gap-y-3">
        <span className="text-sm font-semibold flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-lce-orange" />
          Autonomy, last 30 days
        </span>
        <span className="text-sm"><b className="text-lg tabular-nums">{health.t0_auto}</b> <span className="text-text-secondary">auto-published</span></span>
        <span className="text-sm">
          <b className="text-lg tabular-nums">{health.t1_approved_no_edit_pct !== null ? `${health.t1_approved_no_edit_pct.toFixed(0)}%` : 'n/a'}</b>{' '}
          <span className="text-text-secondary">approved without edits</span>
        </span>
        <span className="text-sm"><b className="text-lg tabular-nums">{health.t2_reviews}</b> <span className="text-text-secondary">reviewed by a person</span></span>
        <span className="text-sm"><b className="text-lg tabular-nums text-red-600">{health.blocked}</b> <span className="text-text-secondary">blocked by brand rules</span></span>
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        <div className="card p-6 lg:col-span-2">
          <div className="flex items-center gap-3 mb-4">
            <div className="icon-tile"><Sparkles className="w-5 h-5" /></div>
            <div>
              <h3 className="font-semibold">Answer Share, weekly</h3>
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
            <h3 className="font-semibold">Ask GEOlogic</h3>
          </div>
          <div className="space-y-3 flex-1 overflow-y-auto max-h-[360px]">
            {messages.length === 0 && (
              <p className="text-sm text-text-tertiary">Ask a question about Answer Share, opportunities, or what changed since the last publish.</p>
            )}
            {messages.map((m, i) => (
              <div
                key={i}
                className={m.role === 'user'
                  ? 'ml-auto max-w-[90%] bg-lce-black text-white rounded-2xl rounded-br-md px-4 py-2.5 text-sm'
                  : 'max-w-[95%] bg-surface-secondary rounded-2xl rounded-bl-md px-4 py-3 text-sm'}
              >
                {m.text}
              </div>
            ))}
            {asking && (
              <div className="max-w-[95%] bg-surface-secondary rounded-2xl rounded-bl-md px-4 py-3 text-sm text-text-tertiary">
                Thinking...
              </div>
            )}
          </div>
          {askError && <p className="text-sm text-red-600 mt-2">{askError}</p>}
          <form className="flex gap-2 mt-4" onSubmit={handleAsk}>
            <input
              aria-label="Ask GEOlogic a question"
              className="flex-1 min-w-0 rounded-xl border border-gray-200 px-3 py-2 text-sm focus:border-lce-orange disabled:opacity-50"
              value={question}
              onChange={e => setQuestion(e.target.value)}
              disabled={asking}
              placeholder="Which engine still gets our prices wrong?"
            />
            <button type="submit" className="btn btn-primary !px-3" aria-label="Ask" disabled={asking}>
              <Send className="w-4 h-4" />
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
