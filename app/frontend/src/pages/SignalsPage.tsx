import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Send, ShieldAlert, MessageCircle, Trophy, Star, Bot } from 'lucide-react'
import { api } from '../api/client'
import type { Signal } from '../api/types'
import { PageSkeleton, ErrorRetry } from '../components/PageState'
import { useToast } from '../components/Toast'
import { Button } from '../components/ui/Button'
import { formatK1, formatTime } from '../lib/format'

type FilterKey = Signal['source_type'] | 'all'

const FILTERS: { key: FilterKey; label: string; icon?: typeof MessageCircle }[] = [
  { key: 'all', label: 'All' },
  { key: 'social', label: 'Social', icon: MessageCircle },
  { key: 'athlete_post', label: 'Athletes', icon: Trophy },
  { key: 'review', label: 'Reviews', icon: Star },
  { key: 'crawler_hit', label: 'AI crawlers', icon: Bot },
]

const SOURCE_ICON: Record<Signal['source_type'], typeof MessageCircle> = {
  social: MessageCircle,
  athlete_post: Trophy,
  review: Star,
  crawler_hit: Bot,
}
const SOURCE_STYLE: Record<Signal['source_type'], string> = {
  social: 'bg-orange-50 text-orange-600',
  athlete_post: 'bg-blue-50 text-blue-600',
  review: 'bg-amber-50 text-amber-600',
  crawler_hit: 'bg-green-50 text-green-600',
}

const SEEDED_OPTIONS = [
  { value: 'S3_kittle', label: 'Kittle tailgate post' },
  { value: 'S4_exclusion', label: 'Excluded athlete trend' },
  { value: 'S5_puffs', label: 'Crazy Puffs thread' },
  { value: 'S5_pretzel', label: 'Pretzel Crust thread' },
  { value: 'S7_crawler', label: 'Crawler gap' },
]

export default function SignalsPage() {
  const toast = useToast()
  const [filter, setFilter] = useState<FilterKey>('all')
  const [seed, setSeed] = useState(SEEDED_OPTIONS[0].value)
  const [newIds, setNewIds] = useState<Set<string>>(new Set())
  const [sending, setSending] = useState(false)
  const seenIds = useRef<Set<string> | null>(null)
  const prevQuarantined = useRef<number | null>(null)

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['signals'],
    queryFn: api.signals,
    refetchInterval: 4000,
  })

  useEffect(() => {
    if (!data) return
    const ids = new Set(data.signals.map(s => s.signal_id))
    if (seenIds.current) {
      const fresh = new Set<string>()
      ids.forEach(id => { if (!seenIds.current!.has(id)) fresh.add(id) })
      setNewIds(fresh)
    }
    seenIds.current = ids

    if (prevQuarantined.current !== null && data.quarantined_count > prevQuarantined.current) {
      toast('1 signal quarantined by an exclusion rule')
    }
    prevQuarantined.current = data.quarantined_count
  }, [data, toast])

  if (isLoading) return <PageSkeleton />
  if (isError || !data) return <ErrorRetry message="Couldn't load Signal Radar." onRetry={() => refetch()} />

  const visible = data.signals.filter(s => filter === 'all' || s.source_type === filter)

  async function sendSignal() {
    setSending(true)
    try {
      await api.inject(seed)
      toast('Signal sent')
      await refetch()
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-end justify-between flex-wrap gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-lce-orange-dark mb-1">Monitor</p>
          <h2 className="text-2xl font-semibold">Signal Radar</h2>
          <p className="text-text-secondary">Social, athlete, review, and AI-crawler signals matched to the menu as they arrive</p>
        </div>
        <div className="flex items-center gap-2 text-sm text-text-secondary">
          <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
          Streaming
        </div>
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        <div className="card p-6 lg:col-span-2">
          <div className="flex flex-wrap gap-2 mb-4 bg-surface-secondary rounded-2xl p-1.5 w-fit">
            {FILTERS.map(f => (
              <button
                key={f.key}
                onClick={() => setFilter(f.key)}
                className={`nav-item !py-1.5 ${filter === f.key ? 'active' : ''}`}
              >
                {f.icon && <f.icon className="w-4 h-4" />}
                {f.label}
              </button>
            ))}
          </div>
          <div className="space-y-3">
            {visible.map(s => (
              <SignalCard key={s.signal_id} signal={s} isNew={newIds.has(s.signal_id)} />
            ))}
            {visible.length === 0 && (
              <p className="text-sm text-text-tertiary py-8 text-center">No signals in this filter yet.</p>
            )}
          </div>
        </div>

        <div className="space-y-6">
          <div className="rounded-2xl p-5 bg-red-50 border border-red-100 flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-red-100 flex items-center justify-center text-red-600">
              <ShieldAlert className="w-6 h-6" />
            </div>
            <div>
              <p className="text-3xl font-bold text-red-700 tabular-nums">{data.quarantined_count}</p>
              <p className="text-sm text-red-700">quarantined at ingest by exclusion rules. Hidden from the feed, logged for Brand and Legal.</p>
            </div>
          </div>

          <div className="card p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="icon-tile"><Send className="w-5 h-5" /></div>
              <div>
                <h3 className="font-semibold">Send a signal</h3>
                <p className="text-sm text-text-secondary">Presenter control</p>
              </div>
            </div>
            <select
              aria-label="Seeded signal"
              className="w-full rounded-xl border border-gray-200 px-3 py-2 text-sm bg-white mb-3"
              value={seed}
              onChange={e => setSeed(e.target.value)}
            >
              {SEEDED_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
            <Button variant="secondary" className="w-full" icon={<Send className="w-4 h-4" />} loading={sending} onClick={sendSignal}>
              Send signal
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}

function SignalCard({ signal, isNew }: { signal: Signal; isNew: boolean }) {
  const Icon = SOURCE_ICON[signal.source_type]
  return (
    <article className={`flex gap-4 p-4 rounded-xl border border-gray-100 bg-white hover:shadow-soft transition-all ${isNew ? 'animate-slide-up ring-1 ring-lce-orange/30' : ''}`}>
      <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${SOURCE_STYLE[signal.source_type]}`}>
        <Icon className="w-5 h-5" />
      </div>
      <div className="flex-1 min-w-0 space-y-2">
        <div className="flex flex-wrap items-center gap-x-2 text-sm">
          <b className="font-medium">{signal.author}</b>
          {signal.reach !== null && <span className="text-text-tertiary">{formatK1(signal.reach)}</span>}
          {signal.velocity !== null && <span className="text-text-tertiary">velocity {signal.velocity.toFixed(1)}×</span>}
          <span className="ml-auto font-mono text-xs text-text-tertiary">{formatTime(signal.ingested_at)}</span>
        </div>
        <p className="text-sm">{signal.text}</p>
        {signal.image_url && (
          <div className="flex items-end gap-3 flex-wrap">
            <div className="thumb w-36 aspect-[4/3] rounded-xl relative overflow-hidden">
              <img src={signal.image_url} alt="" className="absolute inset-0 w-full h-full object-cover" />
              {signal.image_match_score !== null && (
                <span className="absolute left-1.5 bottom-1.5 text-[10px] font-mono bg-black/60 text-white px-1.5 rounded">
                  {signal.menu_item_name ?? 'Menu match'} · {signal.image_match_score.toFixed(2)} match
                </span>
              )}
            </div>
            <span className="text-xs text-text-tertiary">Image described and matched to the menu</span>
          </div>
        )}
        <div className="flex flex-wrap gap-1.5">
          {signal.menu_item_name && <span className="badge b-info"><span className="dot" />{signal.menu_item_name}</span>}
          {signal.persona_name && <span className="badge b-warning"><span className="dot" />Person association · T2</span>}
          {signal.sentiment && (
            <span className={`badge ${signal.sentiment === 'negative' ? 'b-error' : signal.sentiment === 'positive' ? 'b-success' : 'b-default'}`}>
              <span className="dot" />{signal.sentiment.charAt(0).toUpperCase() + signal.sentiment.slice(1)}
            </span>
          )}
          {signal.hits === 0 && <span className="badge b-warning"><span className="dot" />Crawl gap</span>}
        </div>
      </div>
    </article>
  )
}
