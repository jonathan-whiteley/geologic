import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { BadgeAlert, CircleDashed, Flame } from 'lucide-react'
import { api } from '../api/client'
import type { Opportunity } from '../api/types'
import { PageSkeleton, ErrorRetry } from '../components/PageState'
import EvidencePanel from '../components/EvidencePanel'
import DraftPanel from '../components/DraftPanel'
import { formatK } from '../lib/format'

type CategoryKey = 'all' | 'accuracy' | 'gap' | 'moment'

const CATEGORIES: { key: CategoryKey; label: string; icon?: typeof BadgeAlert; types: string[] }[] = [
  { key: 'all', label: 'All', types: [] },
  { key: 'accuracy', label: 'Accuracy', icon: BadgeAlert, types: ['accuracy_fix'] },
  { key: 'gap', label: 'Content gaps', icon: CircleDashed, types: ['content_gap', 'crawler_gap', 'citation_gap'] },
  { key: 'moment', label: 'Moments', icon: Flame, types: ['persona_moment', 'trend'] },
]

const TYPE_BADGE: Record<string, { label: string; variant: 'error' | 'warning' | 'info' | 'default' }> = {
  accuracy_fix: { label: 'Accuracy fix', variant: 'error' },
  content_gap: { label: 'Content gap', variant: 'warning' },
  crawler_gap: { label: 'Content gap', variant: 'warning' },
  citation_gap: { label: 'Citation gap', variant: 'warning' },
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

export default function FixPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [category, setCategory] = useState<CategoryKey>('all')
  const opps = useQuery({ queryKey: ['opps'], queryFn: api.opportunities })
  const sugg = useQuery({ queryKey: ['suggestions'], queryFn: api.suggestions })

  const maxLift = useMemo(() => Math.max(1, ...(opps.data ?? []).map(o => o.expected_lift_high)), [opps.data])

  if (opps.isLoading || sugg.isLoading) return <PageSkeleton statCards={0} />
  if (opps.isError || !opps.data) return <ErrorRetry message="Couldn't load opportunities." onRetry={() => opps.refetch()} />

  const data = opps.data
  const visible = data.filter(o => category === 'all' || categoryOf(o.opp_type) === category)
  const oppParam = searchParams.get('opp')
  const sel = data.find(o => o.opp_id === oppParam) ?? data[0]
  const drafts = (sugg.data ?? []).filter(s => s.opp_id === sel?.opp_id)

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <p className="text-xs font-semibold uppercase tracking-wider text-lce-orange-dark mb-1">Fix</p>
        <h2 className="text-2xl font-semibold">What to fix first</h2>
        <p className="text-text-secondary">Ranked by expected lift. Every fix is drafted by the Content Strategist agent, checked by Brand Guardian, and published only with your approval.</p>
      </div>

      <div className="grid lg:grid-cols-[minmax(320px,5fr)_7fr] gap-6 items-start">
        <div className="space-y-3">
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

          <div className="card p-2 space-y-1">
            {visible.map((o, i) => {
              const badge = TYPE_BADGE[o.opp_type]
              const fresh = freshness(o)
              const isSelected = o.opp_id === sel?.opp_id
              return (
                <button
                  key={o.opp_id}
                  onClick={() => setSearchParams({ opp: o.opp_id }, { replace: true })}
                  className={`w-full text-left p-3 rounded-xl flex gap-3 items-start transition-colors ${isSelected ? 'ring-1 ring-lce-orange/30 bg-lce-orange/5' : 'hover:bg-gray-50'} ${o.status === 'monitor' ? 'opacity-70' : ''}`}
                >
                  <div className={`w-8 h-8 shrink-0 rounded-lg flex items-center justify-center text-sm font-semibold ${i === 0 ? 'lce-gradient text-white shadow-glow-orange' : 'bg-surface-tertiary text-text-secondary'}`}>
                    {o.rank}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium line-clamp-2">{o.title}</p>
                    <div className="flex flex-wrap items-center gap-x-2 gap-y-1 mt-1.5 text-xs">
                      {badge && <span className={`badge b-${badge.variant}`}><span className="dot" />{badge.label}</span>}
                      <span className="font-mono">+{o.expected_lift_low.toFixed(1)} to +{o.expected_lift_high.toFixed(1)}</span>
                      <span className={`font-mono ${fresh.urgent ? 'text-lce-orange font-semibold' : 'text-text-tertiary'}`} title={fresh.top ?? undefined}>{fresh.bottom}</span>
                    </div>
                  </div>
                </button>
              )
            })}
            {visible.length === 0 && <p className="text-sm text-text-tertiary py-8 text-center">No opportunities in this filter.</p>}
          </div>
        </div>

        {sel ? (() => {
          const badge = TYPE_BADGE[sel.opp_type]
          const fresh = freshness(sel)
          return (
            <div className="card p-6 space-y-6">
              <div className="space-y-3">
                <h3 className="font-semibold text-lg">{sel.title}</h3>
                <p className={`text-sm ${sel.status === 'monitor' ? 'text-amber-700' : 'text-text-secondary'}`}>{sel.reasoning}</p>
                <div className="flex flex-wrap gap-1.5">
                  {badge && <span className={`badge b-${badge.variant}`}><span className="dot" />{badge.label}</span>}
                  {sel.assets.map(a => <span key={a} className="badge b-default">{a}</span>)}
                </div>
                <div className="grid sm:grid-cols-[1fr_auto] gap-4 items-end">
                  <div>
                    <p className="text-xs text-text-tertiary mb-1.5">Expected lift · Share of Model pts</p>
                    <div className="relative h-2 rounded-full bg-surface-tertiary">
                      <div
                        className="absolute inset-y-0 rounded-full lce-gradient"
                        style={{ left: `${(sel.expected_lift_low / maxLift) * 100}%`, width: `${((sel.expected_lift_high - sel.expected_lift_low) / maxLift) * 100}%` }}
                      />
                    </div>
                    <p className="font-mono text-sm mt-1.5">+{sel.expected_lift_low.toFixed(1)} to +{sel.expected_lift_high.toFixed(1)}</p>
                    <p className="text-xs text-text-tertiary mt-1">~{formatK(sel.question_volume)} questions/mo</p>
                  </div>
                  <div className="sm:text-right">
                    {fresh.top && <p className="text-xs text-text-tertiary">{fresh.top}</p>}
                    <p className={`font-mono text-lg ${fresh.urgent ? 'text-lce-orange font-semibold' : ''}`}>{fresh.bottom}</p>
                  </div>
                </div>
              </div>

              <EvidencePanel oppId={sel.opp_id} />

              <div className="space-y-4 border-t border-gray-100 pt-5">
                <h3 className="font-semibold">Drafted fix</h3>
                {sugg.isError ? (
                  <ErrorRetry message="Couldn't load the review queue." onRetry={() => sugg.refetch()} />
                ) : drafts.length > 0 ? (
                  <DraftPanel key={sel.opp_id} suggestions={drafts} />
                ) : (
                  <p className="text-sm text-text-tertiary">{sel.status === 'monitor' ? 'No draft: monitoring until the item is available.' : 'No draft yet.'}</p>
                )}
              </div>
            </div>
          )
        })() : (
          <div className="card p-6 text-sm text-text-tertiary text-center">No opportunities yet.</div>
        )}
      </div>
    </div>
  )
}
