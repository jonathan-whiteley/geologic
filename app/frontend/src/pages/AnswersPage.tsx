import type { ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import {
  PieChart, Medal, Link as LinkIcon, BadgeCheck, Grid3x3, Link2, HeartPulse, Download,
  PiggyBank, Timer, ChefHat, Smartphone, Trophy, MessageCircle,
} from 'lucide-react'
import { api } from '../api/client'
import type { ThemeRow } from '../api/types'
import Heatmap from '../components/Heatmap'
import { PageSkeleton, ErrorRetry } from '../components/PageState'

const THEME_ICONS: Record<string, typeof PiggyBank> = {
  value: PiggyBank,
  'speed and convenience': Timer,
  quality: ChefHat,
  'deals and app': Smartphone,
  'game day': Trophy,
}

function themeIcon(label: string) {
  return THEME_ICONS[label.toLowerCase()] ?? MessageCircle
}

function StatCard({ icon, label, value, sub, subClassName = '' }: { icon: ReactNode; label: string; value: string; sub?: ReactNode; subClassName?: string }) {
  return (
    <div className="card p-6 card-hover relative overflow-hidden">
      <div className="absolute top-0 right-0 w-24 h-24 opacity-5">
        <div className="w-full h-full rounded-full bg-lce-orange translate-x-8 -translate-y-8" />
      </div>
      <div className="relative">
        <div className="icon-tile mb-3">{icon}</div>
        <p className="text-sm text-text-secondary mb-1">{label}</p>
        <p className="text-2xl font-semibold tabular-nums">{value}</p>
        {sub && <div className={`flex items-center gap-2 mt-2 text-xs text-text-tertiary ${subClassName}`}>{sub}</div>}
      </div>
    </div>
  )
}

export default function AnswersPage() {
  const navigate = useNavigate()
  const { data, isLoading, isError, refetch } = useQuery({ queryKey: ['model'], queryFn: api.modelSummary })

  if (isLoading) return <PageSkeleton />
  if (isError || !data) return <ErrorRetry message="Couldn't load Share of Model." onRetry={() => refetch()} />

  const { kpis, heatmap, leaderboard, citation_sources, themes, prompt_ids_by_cluster } = data
  const lceRow = leaderboard.find(b => b.brand.toLowerCase().includes('caesar'))
  const topCompetitor = leaderboard.find(b => !b.brand.toLowerCase().includes('caesar'))

  const themesSorted = [...themes].sort((a, b) => a.pct_positive - b.pct_positive)
  const laggingTheme = themesSorted.length >= 2 && themesSorted[0].pct_positive <= themesSorted[1].pct_positive - 10
    ? themesSorted[0]
    : null

  const maxSourceShare = Math.max(1, ...citation_sources.map(s => s.share))
  const typeColors = ['bg-orange-300', 'bg-amber-300', 'bg-gray-400', 'bg-blue-300', 'bg-purple-300', 'bg-teal-300']
  const byType = new Map<string, { label: string; value: number; official: boolean }>()
  for (const s of citation_sources) {
    const cur = byType.get(s.source_type) ?? { label: s.is_official ? 'Official' : s.source_type, value: 0, official: s.is_official }
    cur.value += s.share
    byType.set(s.source_type, cur)
  }
  const typeEntries = [...byType.values()]
  const typeTotal = typeEntries.reduce((a, b) => a + b.value, 0)
  const remainder = Math.max(0, 100 - typeTotal)
  const typeBars = typeEntries.map((e, i) => ({ label: e.label, value: e.value, color: e.official ? 'bg-lce-orange' : typeColors[i % typeColors.length] }))
  if (remainder > 0.5) typeBars.push({ label: 'Reviews and other', value: remainder, color: 'bg-gray-200' })

  function exportLeaderboardCsv() {
    const header = 'Brand,Answer Share,Citation Share\n'
    const rows = leaderboard.map(r => `${r.brand},${r.answer_share.toFixed(2)},${r.citation_share.toFixed(0)}%`).join('\n')
    const blob = new Blob([header + rows], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'leaderboard.csv'
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-end justify-between flex-wrap gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-lce-orange-dark mb-1">Monitor</p>
          <h2 className="text-2xl font-semibold">Share of Model</h2>
          <p className="text-text-secondary">How AI engines answer 150 consumer pizza questions today</p>
        </div>
        <div className="flex items-center gap-2 text-sm text-text-secondary">
          <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
          Last probe {kpis.answers} answers
        </div>
      </div>

      {kpis.answers < 570 && (
        <div className="badge b-warning !text-sm !px-3 !py-2 w-fit">
          <span className="dot" />
          Some engine calls failed in the last probe. Metrics use {kpis.answers} of 600 answers.
        </div>
      )}

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon={<PieChart className="w-5 h-5" />}
          label="Answer Share"
          value={kpis.answer_share.toFixed(2)}
          sub={topCompetitor && <span>{topCompetitor.brand} {topCompetitor.answer_share.toFixed(2)} · named in {kpis.mention_rate.toFixed(0)}%</span>}
        />
        <StatCard
          icon={<Medal className="w-5 h-5" />}
          label="Average rank"
          value={kpis.avg_rank !== null ? kpis.avg_rank.toFixed(1) : 'N/A'}
          sub="when LCE is mentioned"
        />
        <StatCard
          icon={<LinkIcon className="w-5 h-5" />}
          label="Citation rate"
          value={`${kpis.citation_rate.toFixed(0)}%`}
          sub="cites an official LCE page"
        />
        <StatCard
          icon={<BadgeCheck className="w-5 h-5" />}
          label="Fact accuracy"
          value={kpis.fact_accuracy !== null ? `${kpis.fact_accuracy.toFixed(0)}%` : 'N/A'}
          sub={<span className="text-red-600 bg-red-50 px-2 py-0.5 rounded-full font-medium">{kpis.wrong_claims} wrong</span>}
        />
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        <div className="card p-6 lg:col-span-2">
          <div className="flex items-start justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="icon-tile"><Grid3x3 className="w-5 h-5" /></div>
              <div>
                <h3 className="font-semibold">Answer Share by question cluster</h3>
                <p className="text-sm text-text-secondary">Rank-weighted mention rate per engine</p>
              </div>
            </div>
          </div>
          <div className="overflow-x-auto">
            <Heatmap data={heatmap} onCellClick={cluster => {
              const pid = prompt_ids_by_cluster[cluster]
              if (pid) navigate(`/monitor/prompts/${pid}`)
            }} />
          </div>
        </div>

        <div className="card flex flex-col overflow-hidden">
          <div className="flex items-start justify-between p-6 pb-4">
            <div>
              <h3 className="font-semibold">Leaderboard</h3>
              <p className="text-sm text-text-secondary">You versus competitors in AI answers</p>
            </div>
            <button className="w-9 h-9 rounded-xl border border-gray-200 flex items-center justify-center hover:bg-gray-50" title="Export CSV" onClick={exportLeaderboardCsv}>
              <Download className="w-4 h-4" />
            </button>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-y border-gray-100 bg-surface-secondary text-text-secondary">
                <th className="text-left font-medium px-4 py-2.5 whitespace-nowrap">Brand</th>
                <th className="text-right font-medium px-2 py-2.5 whitespace-nowrap">Share ↓</th>
                <th className="text-right font-medium px-4 py-2.5 whitespace-nowrap">Citations</th>
              </tr>
            </thead>
            <tbody>
              {leaderboard.map(row => {
                const isUs = row === lceRow
                return (
                  <tr key={row.brand} className={`border-b border-gray-100 ${isUs ? 'bg-lce-orange/5' : ''}`}>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2.5">
                        <span className="w-8 h-8 rounded-lg bg-white border border-gray-100 flex items-center justify-center overflow-hidden shrink-0">
                          <img src={row.logo} alt="" className="max-w-[26px] max-h-[26px] object-contain" />
                        </span>
                        <span className="font-medium whitespace-nowrap">{row.brand}</span>
                        {isUs && (
                          <span className="whitespace-nowrap text-[11px] font-semibold px-1.5 py-0.5 rounded-md border border-lce-orange/30 bg-lce-cream text-lce-orange-dark">Your brand</span>
                        )}
                      </div>
                    </td>
                    <td className={`px-2 py-3 text-right tabular-nums ${isUs ? 'font-semibold' : ''}`}>{row.answer_share.toFixed(2)}</td>
                    <td className="px-4 py-3 text-right tabular-nums">{row.citation_share.toFixed(0)}%</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        <div className="card p-6 flex flex-col">
          <div className="flex items-center gap-3 mb-4">
            <div className="icon-tile"><Link2 className="w-5 h-5" /></div>
            <div>
              <h3 className="font-semibold">Citation sources</h3>
              <p className="text-sm text-text-secondary">Where engines get their answers</p>
            </div>
          </div>
          <div className="space-y-3">
            {citation_sources.map(s => (
              <div key={s.publisher} className="grid grid-cols-[1fr_auto_48px] items-center gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 text-sm mb-1">
                    <span className={`font-medium truncate ${s.is_official ? 'text-lce-orange-dark' : ''}`}>{s.publisher}</span>
                    <span className={`badge ${s.is_official ? 'b-brand' : 'b-default'}`}>{s.is_official ? 'Official' : s.source_type}</span>
                  </div>
                  <div className="h-1.5 rounded-full bg-surface-tertiary overflow-hidden">
                    <div className={`h-full rounded-full ${s.is_official ? 'lce-gradient' : 'bg-gray-300'}`} style={{ width: `${(s.share / maxSourceShare) * 100}%` }} />
                  </div>
                </div>
                <span />
                <span className={`font-mono text-sm tabular-nums text-right ${s.is_official ? 'text-lce-orange-dark font-semibold' : 'text-text-secondary'}`}>{s.share.toFixed(0)}%</span>
              </div>
            ))}
          </div>
          <div className="mt-auto pt-5">
            <div className="flex h-2.5 rounded-full overflow-hidden">
              {typeBars.map(t => (
                <div key={t.label} className={t.color} style={{ width: `${t.value}%` }} title={`${t.label} ${t.value.toFixed(0)}%`} />
              ))}
            </div>
            <div className="flex flex-wrap gap-x-3 gap-y-1 mt-2 text-xs text-text-secondary">
              {typeBars.map(t => (
                <span key={t.label} className="flex items-center gap-1.5">
                  <i className={`w-2 h-2 rounded-full block ${t.color}`} />
                  {t.label} {t.value.toFixed(0)}%
                </span>
              ))}
            </div>
          </div>
        </div>

        <div className="card p-6 lg:col-span-2">
          <div className="flex items-start justify-between flex-wrap gap-3 mb-4">
            <div className="flex items-center gap-3">
              <div className="icon-tile"><HeartPulse className="w-5 h-5" /></div>
              <div>
                <h3 className="font-semibold">What AI says about us</h3>
                <p className="text-sm text-text-secondary">Sentiment by theme across answers that mention Little Caesars</p>
              </div>
            </div>
            {laggingTheme && (
              <span className="badge b-warning"><span className="dot" />{laggingTheme.label} trails every other theme</span>
            )}
          </div>
          <div className="divide-y divide-gray-100">
            {themes.map((t: ThemeRow) => {
              const Icon = themeIcon(t.label)
              const rest = Math.max(0, 100 - t.pct_positive - t.pct_negative)
              return (
                <div key={t.theme} className="grid grid-cols-[170px_1fr_64px] items-center gap-4 py-3">
                  <div className="flex items-center gap-2">
                    <Icon className="w-4 h-4 text-lce-orange" />
                    <span className="text-sm font-medium">{t.label}</span>
                  </div>
                  <div className="min-w-0">
                    <div className="flex h-2 rounded-full overflow-hidden bg-gray-200">
                      <div className="bg-green-500" style={{ width: `${t.pct_positive}%` }} />
                      <div className="bg-gray-300" style={{ width: `${rest}%` }} />
                      <div className="bg-red-400" style={{ width: `${t.pct_negative}%` }} />
                    </div>
                    <p className="text-xs text-text-tertiary mt-1.5 truncate">&quot;{t.sample_quote}&quot; · {t.answers} answers</p>
                  </div>
                  <span className={`text-right font-semibold tabular-nums ${t.pct_positive < 60 ? 'text-amber-700' : ''}`}>{t.pct_positive.toFixed(0)}%</span>
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}
