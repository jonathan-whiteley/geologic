import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { BadgeAlert, CircleDashed, Flame } from 'lucide-react'
import { api } from '../api/client'
import type { Opportunity } from '../api/types'
import { PageSkeleton, ErrorRetry } from '../components/PageState'
import { formatK } from '../lib/format'

type CategoryKey = 'all' | 'accuracy' | 'gap' | 'moment'

const CATEGORIES: { key: CategoryKey; label: string; icon?: typeof BadgeAlert; types: string[] }[] = [
  { key: 'all', label: 'All', types: [] },
  { key: 'accuracy', label: 'Accuracy', icon: BadgeAlert, types: ['accuracy_fix'] },
  { key: 'gap', label: 'Content gaps', icon: CircleDashed, types: ['content_gap', 'crawler_gap'] },
  { key: 'moment', label: 'Moments', icon: Flame, types: ['persona_moment', 'trend'] },
]

const TYPE_BADGE: Record<string, { label: string; variant: 'error' | 'warning' | 'info' | 'default' }> = {
  accuracy_fix: { label: 'Accuracy fix', variant: 'error' },
  content_gap: { label: 'Content gap', variant: 'warning' },
  crawler_gap: { label: 'Content gap', variant: 'warning' },
  persona_moment: { label: 'Person moment', variant: 'info' },
  trend: { label: 'Trend', variant: 'info' },
}

function categoryOf(oppType: string): CategoryKey {
  const found = CATEGORIES.find(c => c.types.includes(oppType))
  return found?.key ?? 'all'
}

function freshness(o: Opportunity) {
  if (!o.window_expires_at) return { top: o.window_name, bottom: 'No expiry', urgent: false }
  const ms = new Date(o.window_expires_at).getTime() - Date.now()
  if (ms <= 0) return { top: o.window_name, bottom: 'Expired', urgent: false }
  const hours = ms / 3_600_000
  if (hours < 48) return { top: o.window_name, bottom: `${Math.max(1, Math.round(hours))}h`, urgent: true }
  return { top: o.window_name, bottom: `${Math.round(hours / 24)}d`, urgent: false }
}

export default function PrioritizePage() {
  const navigate = useNavigate()
  const [category, setCategory] = useState<CategoryKey>('all')
  const { data, isLoading, isError, refetch } = useQuery({ queryKey: ['opps'], queryFn: api.opportunities })

  const maxLift = useMemo(() => Math.max(1, ...(data ?? []).map(o => o.expected_lift_high)), [data])

  if (isLoading) return <PageSkeleton statCards={0} />
  if (isError || !data) return <ErrorRetry message="Couldn't load Opportunities." onRetry={() => refetch()} />

  const visible = data.filter(o => category === 'all' || categoryOf(o.opp_type) === category)

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <p className="text-xs font-semibold uppercase tracking-wider text-lce-orange-dark mb-1">Prioritize</p>
        <h2 className="text-2xl font-semibold">Opportunities</h2>
        <p className="text-text-secondary">Ranked by expected lift: answer gap × question volume × demand calendar × margin × availability</p>
      </div>

      <div className="flex flex-wrap gap-2 bg-surface-secondary rounded-2xl p-1.5 w-fit">
        {CATEGORIES.map(c => (
          <button
            key={c.key}
            onClick={() => setCategory(c.key)}
            className={`nav-item !py-1.5 ${category === c.key ? 'active' : ''}`}
          >
            {c.icon && <c.icon className="w-4 h-4" />}
            {c.label}
          </button>
        ))}
      </div>

      <div className="space-y-3">
        {visible.map((o, i) => {
          const badge = TYPE_BADGE[o.opp_type]
          const fresh = freshness(o)
          const isMonitor = o.status === 'monitor'
          return (
            <button
              key={o.opp_id}
              onClick={() => navigate(`/act?opp=${o.opp_id}`)}
              className={`card card-hover w-full text-left p-5 grid md:grid-cols-[48px_1fr_220px_140px] gap-5 items-center ${isMonitor ? 'opacity-70' : ''}`}
            >
              <div className={`w-10 h-10 rounded-xl flex items-center justify-center font-semibold ${i === 0 ? 'lce-gradient text-white shadow-glow-orange' : 'bg-surface-tertiary text-text-secondary'}`}>
                {o.rank}
              </div>
              <div className="min-w-0">
                <h3 className="font-semibold">{o.title}</h3>
                <p className={`text-sm mt-0.5 ${isMonitor ? 'text-amber-700' : 'text-text-secondary'}`}>{o.reasoning}</p>
                <div className="flex flex-wrap gap-1.5 mt-2.5">
                  {badge && <span className={`badge b-${badge.variant}`}><span className="dot" />{badge.label}</span>}
                  {o.assets.map(a => <span key={a} className="badge b-default">{a}</span>)}
                </div>
              </div>
              <div>
                <p className="text-xs text-text-tertiary mb-1.5">Expected lift · Answer Share pts</p>
                <div className="relative h-2 rounded-full bg-surface-tertiary">
                  <div
                    className="absolute inset-y-0 rounded-full lce-gradient"
                    style={{ left: `${(o.expected_lift_low / maxLift) * 100}%`, width: `${((o.expected_lift_high - o.expected_lift_low) / maxLift) * 100}%` }}
                  />
                </div>
                <p className="font-mono text-sm mt-1.5">+{o.expected_lift_low.toFixed(1)} to +{o.expected_lift_high.toFixed(1)}</p>
                <p className="text-xs text-text-tertiary mt-1">~{formatK(o.question_volume)} questions/mo</p>
              </div>
              <div>
                {fresh.top && <p className="text-xs text-text-tertiary">{fresh.top}</p>}
                <p className={`font-mono text-lg ${fresh.urgent ? 'text-lce-orange font-semibold' : ''}`}>{fresh.bottom}</p>
              </div>
            </button>
          )
        })}
        {visible.length === 0 && <p className="text-sm text-text-tertiary py-8 text-center">No opportunities in this filter.</p>}
      </div>
    </div>
  )
}
