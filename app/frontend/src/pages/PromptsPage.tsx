import { useMemo, useState, type FormEvent, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router-dom'
import {
  Search, ChevronDown, BookmarkPlus, Download, MessageSquareQuote,
} from 'lucide-react'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, ResponsiveContainer,
} from 'recharts'
import { api } from '../api/client'
import type { Claim, EngineAnswerT, RelatedPrompt } from '../api/types'
import { PageSkeleton, ErrorRetry } from '../components/PageState'
import { useToast } from '../components/Toast'
import { Button } from '../components/ui/Button'
import { CLUSTERS } from '../components/Heatmap'
import { formatDate, formatK1 } from '../lib/format'

const CLUSTER_LABEL = new Map(CLUSTERS)

function monthLabel(month: string): string {
  const d = new Date(`${month}-01T00:00:00`)
  if (Number.isNaN(d.getTime())) return month
  return d.toLocaleDateString('en-US', { month: 'short' })
}

function monthYear(month: string): string {
  const d = new Date(`${month}-01T00:00:00`)
  if (Number.isNaN(d.getTime())) return month
  return d.toLocaleDateString('en-US', { month: 'short', year: 'numeric' })
}

function highlightTruth(text: string): ReactNode[] {
  const parts = text.split(/(\$\d+(?:\.\d{2})?)/g)
  return parts.map((p, i) => /^\$\d/.test(p) ? <b key={i} className="font-mono text-text-primary">{p}</b> : <span key={i}>{p}</span>)
}

function renderAnswer(answer: string, claims: Claim[]): ReactNode[] {
  type Seg = { start: number; end: number; verdict: Claim['verdict'] }
  const segs: Seg[] = []
  for (const c of claims) {
    if (c.verdict === 'unverifiable') continue
    const idx = answer.indexOf(c.price)
    if (idx === -1) continue
    segs.push({ start: idx, end: idx + c.price.length, verdict: c.verdict })
  }
  segs.sort((a, b) => a.start - b.start)
  const clean: Seg[] = []
  let cursor = 0
  for (const s of segs) {
    if (s.start < cursor) continue
    clean.push(s)
    cursor = s.end
  }
  const nodes: ReactNode[] = []
  let pos = 0
  clean.forEach((s, i) => {
    if (s.start > pos) nodes.push(<span key={`t${i}`}>{answer.slice(pos, s.start)}</span>)
    nodes.push(<mark key={`m${i}`} className={s.verdict === 'wrong' ? 'bad' : 'ok'}>{answer.slice(s.start, s.end)}</mark>)
    pos = s.end
  })
  if (pos < answer.length) nodes.push(<span key="tail">{answer.slice(pos)}</span>)
  return nodes
}

function answerStatus(a: EngineAnswerT) {
  if (a.lce_rank === null) return { label: 'Little Caesars missing', variant: 'error' as const }
  if (a.claims.some(c => c.verdict === 'wrong')) return { label: '1 wrong claim · stale price', variant: 'error' as const }
  return { label: 'All claims correct', variant: 'success' as const }
}

function csvDownload(filename: string, header: string, rows: string) {
  const blob = new Blob([header + rows], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export default function PromptsPage() {
  const { promptId: routePromptId } = useParams()
  const navigate = useNavigate()
  const toast = useToast()
  const [query, setQuery] = useState('')
  const [searchError, setSearchError] = useState<string | null>(null)
  const [searching, setSearching] = useState(false)
  const [engineFilter, setEngineFilter] = useState('all')
  const [trackingOverride, setTrackingOverride] = useState<Record<string, boolean>>({})
  const [tracked, setTracked] = useState<boolean | null>(null)
  const [trackingSelf, setTrackingSelf] = useState(false)

  const { data: model } = useQuery({ queryKey: ['model'], queryFn: api.modelSummary })
  const promptId = routePromptId ?? model?.drill_prompt_id

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['prompt', promptId],
    queryFn: () => api.promptExplorer(promptId as string),
    enabled: !!promptId,
  })

  const isTracked = tracked ?? data?.tracked ?? false

  const chartData = useMemo(() => (data?.series ?? []).map(s => ({
    month: s.month,
    label: monthLabel(s.month),
    est_volume: s.est_volume,
  })), [data?.series])

  const febPoint = chartData.find(d => new Date(`${d.month}-01T00:00:00`).getMonth() === 1)

  async function handleSearch(e: FormEvent) {
    e.preventDefault()
    const q = query.trim()
    if (!q) {
      setSearchError('Type a question to research.')
      return
    }
    setSearching(true)
    setSearchError(null)
    try {
      const res = await api.promptSearch(q)
      navigate(`/monitor/prompts/${res.prompt_id}`)
      toast('Probed 4 engines')
    } catch (err) {
      setSearchError(err instanceof Error ? err.message : 'Something went wrong.')
    } finally {
      setSearching(false)
    }
  }

  async function handleTrackSelf() {
    if (!promptId || isTracked) return
    setTrackingSelf(true)
    try {
      await api.trackPrompt(promptId)
      setTracked(true)
    } finally {
      setTrackingSelf(false)
    }
  }

  async function handleTrackRelated(r: RelatedPrompt) {
    await api.trackPrompt(r.prompt_id)
    setTrackingOverride(prev => ({ ...prev, [r.prompt_id]: true }))
    toast('Prompt added to the probe bank')
  }

  function exportVolumeCsv() {
    const header = 'Month,Estimated Volume\n'
    const rows = chartData.map(d => `${d.month},${d.est_volume}`).join('\n')
    csvDownload('question-volume.csv', header, rows)
  }

  const engines = useMemo(() => {
    const set = new Set((data?.answers ?? []).map(a => a.engine))
    return [...set]
  }, [data?.answers])

  const filteredAnswers = (data?.answers ?? []).filter(a => engineFilter === 'all' || a.engine === engineFilter)

  return (
    <div className="space-y-6 animate-fade-in">
      <form className="flex gap-3 flex-wrap" onSubmit={handleSearch}>
        <div className="relative flex-1 min-w-[260px] max-w-2xl">
          <Search className="w-4 h-4 text-text-tertiary absolute left-4 top-1/2 -translate-y-1/2" />
          <input
            aria-label="Search a prompt"
            className="w-full rounded-xl border border-gray-200 bg-white pl-11 pr-4 py-3 text-sm focus:border-lce-orange"
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="How much is a Little Caesars Hot-N-Ready pizza right now?"
          />
        </div>
        <Button type="submit" icon={<Search className="w-4 h-4" />} loading={searching} className="!px-5">
          Research
        </Button>
      </form>
      {searchError && <p className="text-sm text-red-600">{searchError}</p>}

      {isLoading || !data ? (
        isError ? <ErrorRetry message="Couldn't load this question." onRetry={() => refetch()} /> : <PageSkeleton statCards={4} />
      ) : (
        <>
          <div className="flex items-start justify-between flex-wrap gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-lce-orange-dark mb-1">Monitor</p>
              <h2 className="text-2xl font-semibold">{data.prompt_text}</h2>
              <p className="text-text-secondary text-sm mt-1">
                First tracked {formatDate(data.first_tracked)} · Updated {formatDate(data.updated_at)} · {CLUSTER_LABEL.get(data.cluster) ?? data.cluster}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <div className="inline-flex items-center gap-2 rounded-xl border border-lce-orange/40 bg-lce-cream px-3 py-2 text-sm">
                <span className="text-text-secondary">Engine:</span>
                <select
                  className="bg-transparent font-medium focus:outline-none"
                  value={engineFilter}
                  onChange={e => setEngineFilter(e.target.value)}
                  aria-label="Filter by engine"
                >
                  <option value="all">All engines</option>
                  {engines.map(e => <option key={e} value={e}>{e}</option>)}
                </select>
                <ChevronDown className="w-4 h-4 text-text-secondary" />
              </div>
              <Button
                variant="secondary"
                icon={<BookmarkPlus className="w-4 h-4" />}
                disabled={isTracked}
                loading={trackingSelf}
                onClick={handleTrackSelf}
              >
                {isTracked ? 'Tracked' : 'Track prompt'}
              </Button>
              <button className="w-10 h-10 rounded-xl border border-gray-200 bg-white flex items-center justify-center hover:bg-gray-50" title="Export" onClick={exportVolumeCsv}>
                <Download className="w-4 h-4" />
              </button>
            </div>
          </div>

          <div className="card grid grid-cols-2 lg:grid-cols-4 divide-x divide-gray-100">
            <div className="p-5">
              <p className="text-sm text-text-secondary">Avg. monthly volume</p>
              <p className="text-3xl font-semibold tabular-nums mt-1">{formatK1(data.kpis.avg_monthly_volume)}</p>
            </div>
            <div className="p-5">
              <p className="text-sm text-text-secondary">Usage frequency</p>
              <p className={`text-3xl font-semibold tabular-nums mt-1 ${data.kpis.volume_tier === 'High' ? 'text-green-700' : 'text-amber-700'}`}>{data.kpis.volume_tier}</p>
            </div>
            <div className="p-5">
              <p className="text-sm text-text-secondary">Answer Share</p>
              <p className="text-3xl font-semibold tabular-nums mt-1">{data.kpis.answer_share !== null ? data.kpis.answer_share.toFixed(2) : 'N/A'}</p>
            </div>
            <div className="p-5">
              <p className="text-sm text-text-secondary">Engines naming LCE</p>
              <p className={`text-3xl font-semibold tabular-nums mt-1 ${data.kpis.engines_naming <= 1 ? 'text-red-600' : ''}`}>
                {data.kpis.engines_naming} of {data.kpis.engines_answered}
              </p>
            </div>
          </div>

          <div className="grid lg:grid-cols-3 gap-6">
            <div className="card p-6 lg:col-span-2">
              <div className="flex items-start justify-between mb-2">
                <div>
                  <h3 className="font-semibold">Question volume over time</h3>
                  <p className="text-sm text-text-secondary">Estimated monthly AI questions, last 12 months</p>
                </div>
                <button className="w-9 h-9 rounded-xl border border-gray-200 flex items-center justify-center hover:bg-gray-50" title="Export" onClick={exportVolumeCsv}>
                  <Download className="w-4 h-4" />
                </button>
              </div>
              <div className="h-[240px]">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                    <defs>
                      <linearGradient id="volGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#FF671B" stopOpacity={0.22} />
                        <stop offset="100%" stopColor="#FF671B" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 4" vertical={false} stroke="#F0F1F2" />
                    <XAxis dataKey="label" tick={{ fontSize: 11, fill: '#9CA3AF' }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fontSize: 11, fill: '#9CA3AF' }} axisLine={false} tickLine={false} tickFormatter={formatK1} width={40} />
                    <Tooltip
                      content={({ active, payload }) => {
                        if (!active || !payload?.length) return null
                        const p = payload[0].payload as { month: string; est_volume: number }
                        return (
                          <div className="custom-tooltip text-sm">
                            <p className="text-text-secondary text-xs">{monthYear(p.month)}</p>
                            <p className="font-medium flex items-center gap-2">
                              <span className="w-2 h-2 rounded-full bg-lce-orange" />
                              {p.est_volume.toLocaleString()} questions
                            </p>
                          </div>
                        )
                      }}
                    />
                    {febPoint && (
                      <ReferenceLine x={febPoint.label} stroke="#E0530F" strokeDasharray="2 3" opacity={0.6}
                        label={{ value: 'Super Bowl', position: 'insideBottomLeft', fill: '#E0530F', fontSize: 11 }} />
                    )}
                    <Area type="monotone" dataKey="est_volume" stroke="#FF671B" strokeWidth={2.5} fill="url(#volGradient)" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="card p-6">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-semibold flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-lce-orange" />
                  Related prompts
                </h3>
                <span className="text-xs text-text-tertiary">Semantic</span>
              </div>
              <div className="divide-y divide-gray-100">
                {data.related.map(r => {
                  const tracking = trackingOverride[r.prompt_id] ?? r.status === 'tracking'
                  return (
                    <div key={r.prompt_id} className="py-2.5 flex items-center gap-3">
                      <button className="flex-1 min-w-0 text-left" onClick={() => navigate(`/monitor/prompts/${r.prompt_id}`)}>
                        <p className="text-sm leading-snug">{r.prompt_text}</p>
                        <p className="text-xs text-text-tertiary mt-0.5">{formatK1(r.avg_monthly_volume)} / mo</p>
                      </button>
                      {r.status === 'closest' ? (
                        <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-lce-cream text-lce-orange-dark whitespace-nowrap">Closest</span>
                      ) : tracking ? (
                        <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-green-50 text-green-700 whitespace-nowrap">Tracking</span>
                      ) : (
                        <button
                          className="text-xs font-semibold px-2.5 py-1 rounded-full border border-gray-300 hover:bg-gray-50 whitespace-nowrap"
                          onClick={() => handleTrackRelated(r)}
                        >
                          + Track
                        </button>
                      )}
                    </div>
                  )
                })}
              </div>
              <p className="text-xs text-text-tertiary mt-3">Found with Vector Search over the question bank</p>
            </div>
          </div>

          <div className="card p-6">
            <div className="flex items-start justify-between flex-wrap gap-3 mb-4">
              <div className="flex items-center gap-3">
                <div className="icon-tile"><MessageSquareQuote className="w-5 h-5" /></div>
                <div>
                  <h3 className="font-semibold">How engines answer</h3>
                  {data.menu_truth && <p className="text-sm text-text-secondary">{highlightTruth(data.menu_truth)}</p>}
                </div>
              </div>
              <div className="flex gap-2">
                <span className="badge b-default"><span className="dot" />{CLUSTER_LABEL.get(data.cluster) ?? data.cluster}</span>
                {data.kpis.engines_naming === 0 && <span className="badge b-error"><span className="dot" />Content gap</span>}
              </div>
            </div>
            <div className="grid md:grid-cols-2 gap-4">
              {filteredAnswers.map(a => {
                const status = answerStatus(a)
                return (
                  <div key={a.engine} className={`rounded-xl border ${status.variant === 'success' ? 'border-green-100' : 'border-gray-100'} bg-surface-secondary p-4 space-y-2.5`}>
                    <div className="flex items-center gap-2">
                      <span className="badge b-info">{a.engine}</span>
                      <span className="ml-auto font-mono text-xs text-text-tertiary">{a.lce_rank ? `LCE rank ${a.lce_rank}` : 'LCE not mentioned'}</span>
                    </div>
                    <p className="text-sm">{a.answer ? renderAnswer(a.answer, a.claims) : <span className="text-text-tertiary">No answer captured.</span>}</p>
                    <div className="flex flex-wrap gap-1.5">
                      {a.cited.map(c => (
                        <span key={c.doc_id} className={`font-mono text-[11px] px-2 py-0.5 rounded-md ${c.is_official ? 'bg-lce-orange/10 text-lce-orange-dark' : 'bg-white text-text-secondary border border-gray-100'}`}>
                          {c.doc_id}
                        </span>
                      ))}
                    </div>
                    <span className={`badge b-${status.variant}`}><span className="dot" />{status.label}</span>
                  </div>
                )
              })}
              {filteredAnswers.length === 0 && (
                <p className="text-sm text-text-tertiary py-6 text-center md:col-span-2">No answers for this engine filter.</p>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
