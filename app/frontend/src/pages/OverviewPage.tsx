import { useQuery } from '@tanstack/react-query'
import { BadgeCheck, Download, Eye, Grid3x3, Link as LinkIcon, Link2, PieChart, ShieldCheck } from 'lucide-react'
import { api } from '../api/client'
import type { BrandRow } from '../api/types'
import { formatTime, fx } from '../lib/format'
import { ownerChip } from '../lib/owners'
import Heatmap from '../components/Heatmap'
import KpiCard from '../components/KpiCard'
import CitationPizza from '../components/CitationPizza'
import { PageSkeleton, ErrorRetry } from '../components/PageState'

const isLce = (b: BrandRow) => b.brand.toLowerCase().includes('caesar')

export default function OverviewPage() {
  const summary = useQuery({ queryKey: ['model'], queryFn: api.modelSummary })

  if (summary.isLoading) return <PageSkeleton />
  if (summary.isError || !summary.data) return <ErrorRetry message="Couldn't load Measure." onRetry={() => summary.refetch()} />

  const { kpis, brands, heatmap, source_types, top_domains, gateway } = summary.data
  const expected = kpis.tracked_prompts * kpis.engines
  const competitors = brands.filter(b => !isLce(b))

  // Our pages first, then the top unowned domains, each as a share of all citations.
  const totalCitations = source_types.reduce((a, s) => a + s.citations, 0) || 1
  const owned = source_types.find(s => s.owner_class === 'Owned')
  const sources = [
    ...(owned ? [{ key: 'owned', label: 'Little Caesars pages', owner: 'Owned', share: owned.share, citations: owned.citations, prompts: null as number | null }] : []),
    ...top_domains.map(d => ({ key: d.domain, label: d.domain, owner: d.owner_class, share: (d.citations / totalCitations) * 100, citations: d.citations, prompts: d.prompts as number | null })),
  ]
  const maxShare = Math.max(1, ...sources.map(s => s.share))
  const slices = source_types.filter(s => s.share > 0)
    .map(s => ({ label: s.owner_class, value: s.share, official: s.owner_class === 'Owned' }))

  function exportLeaderboardCsv() {
    const header = 'Brand,Share of Model,Avg position,Citation share\n'
    const rows = brands.map(r => `${r.brand},${fx(r.answer_share)},${fx(r.avg_position, 1)},${fx(r.citation_share, 0, '%')}`).join('\n')
    const url = URL.createObjectURL(new Blob([header + rows], { type: 'text/csv' }))
    const a = document.createElement('a')
    a.href = url
    a.download = 'leaderboard.csv'
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <p className="text-xs font-semibold uppercase tracking-wider text-lce-orange-dark mb-1">Measure</p>
        <h2 className="text-2xl font-semibold">What AI says when customers ask about us</h2>
        <p className="text-text-secondary">Simulated web, so we can show cause and effect live.</p>
      </div>

      <div className="card px-5 py-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
        <span className="flex items-center gap-2 font-medium">
          <ShieldCheck className="w-4 h-4 text-lce-orange" />
          {kpis.tracked_prompts} tracked prompts · {kpis.engines} engines via AI Gateway · {kpis.answers} answers
          {kpis.last_run_at && <> · last run {formatTime(kpis.last_run_at)}</>}
          {typeof gateway?.logged === 'number' && gateway.logged > 0 && <> · {gateway.logged.toLocaleString()} requests logged by AI Gateway</>}
        </span>
      </div>

      {kpis.answers < expected && (
        <div className="badge b-warning !text-sm !px-3 !py-2 w-fit">
          <span className="dot" />
          Some engine calls failed. Metrics use {kpis.answers} of {expected} answers.
        </div>
      )}

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard icon={<PieChart className="w-5 h-5" />} label="Share of Model" value={fx(kpis.answer_share)}
          subtitle="Share of Voice, weighted by rank" title="Being named first counts most."
          sub={competitors.length > 0 && <span>{competitors.map(c => `${c.brand} ${fx(c.answer_share)}`).join(' · ')}</span>} />
        <KpiCard icon={<Eye className="w-5 h-5" />} label="Visibility" value={fx(kpis.mention_rate, 0, '%')}
          sub="of answers to unbranded prompts name LCE" />
        <KpiCard icon={<LinkIcon className="w-5 h-5" />} label="Owned citation share" value={fx(kpis.owned_citation_share, 0, '%')}
          sub="of citations point to LCE pages · aim for 20%+" />
        <KpiCard icon={<BadgeCheck className="w-5 h-5" />} label="Fact accuracy" value={fx(kpis.fact_accuracy, 0, '%')}
          subtitle="checked against Unity Catalog facts"
          sub={<>
            <span className="text-red-700 bg-red-50 px-2 py-0.5 rounded-full font-medium">{kpis.wrong_claims} wrong</span>
            <span className="text-amber-700 bg-amber-50 px-2 py-0.5 rounded-full font-medium">{kpis.outdated_claims} outdated</span>
          </>} />
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        <div className="card p-6 lg:col-span-2">
          <div className="flex items-center gap-3 mb-4">
            <div className="icon-tile"><Grid3x3 className="w-5 h-5" /></div>
            <div>
              <h3 className="font-semibold">Share of Model by cluster and engine</h3>
              <p className="text-sm text-text-secondary">Rank-weighted mention rate on unbranded tracked prompts</p>
            </div>
          </div>
          <div className="overflow-x-auto">
            <Heatmap data={heatmap} />
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
                <th className="text-right font-medium px-2 py-2.5 whitespace-nowrap" title="Average position when named">Pos.</th>
                <th className="text-right font-medium px-4 py-2.5 whitespace-nowrap">Citations</th>
              </tr>
            </thead>
            <tbody>
              {brands.map(row => {
                const us = isLce(row)
                return (
                  <tr key={row.brand} className={`border-b border-gray-100 last:border-0 ${us ? 'bg-lce-orange/5' : ''}`}>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2.5">
                        <span className="w-8 h-8 rounded-lg bg-surface border border-gray-100 flex items-center justify-center overflow-hidden shrink-0">
                          <img src={row.logo} alt="" className="max-w-[26px] max-h-[26px] object-contain" />
                        </span>
                        <span className="font-medium whitespace-nowrap">{row.brand}</span>
                        {us && (
                          <span className="whitespace-nowrap text-[11px] font-semibold px-1.5 py-0.5 rounded-md border border-lce-orange/30 bg-lce-cream text-lce-orange-dark">Your brand</span>
                        )}
                      </div>
                    </td>
                    <td className={`px-2 py-3 text-right tabular-nums ${us ? 'font-semibold' : ''}`}>{fx(row.answer_share)}</td>
                    <td className="px-2 py-3 text-right tabular-nums text-text-secondary">{fx(row.avg_position, 1)}</td>
                    <td className="px-4 py-3 text-right tabular-nums">{fx(row.citation_share, 0, '%')}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card p-6">
        <div className="flex items-center gap-3 mb-5">
          <div className="icon-tile"><Link2 className="w-5 h-5" /></div>
          <div>
            <h3 className="font-semibold">Citation sources</h3>
            <p className="text-sm text-text-secondary">Where engines get their answers: our pages and the top unowned domains</p>
          </div>
        </div>
        <div className="grid lg:grid-cols-[3fr_2fr] gap-8 items-center">
          <div className="space-y-3">
            {sources.map(s => {
              const us = s.owner === 'Owned'
              return (
                <div key={s.key} className="grid grid-cols-[1fr_auto] items-center gap-4"
                  title={`${s.citations} citations${s.prompts != null ? ` across ${s.prompts} prompts` : ''}`}>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 text-sm mb-1">
                      <span className={`font-medium truncate ${us ? 'text-lce-orange-dark' : ''}`}>{s.label}</span>
                      <span className={`badge ${ownerChip(s.owner)}`}>{us ? 'Official' : s.owner}</span>
                      {s.prompts != null && <span className="text-xs text-text-tertiary whitespace-nowrap">{s.prompts} prompts</span>}
                    </div>
                    <div className="h-1.5 rounded-full bg-surface-tertiary overflow-hidden">
                      <div className={`h-full rounded-full ${us ? 'lce-gradient' : 'bg-gray-300'}`} style={{ width: `${(s.share / maxShare) * 100}%` }} />
                    </div>
                  </div>
                  <span className={`font-mono text-sm tabular-nums text-right w-12 ${us ? 'text-lce-orange-dark font-semibold' : 'text-text-secondary'}`}>{fx(s.share, 0, '%')}</span>
                </div>
              )
            })}
            {sources.length === 0 && <p className="text-sm text-text-tertiary">No citations yet.</p>}
          </div>
          {slices.length > 0 && (
            <div className="lg:border-l lg:border-gray-100 lg:pl-8">
              <CitationPizza slices={slices} />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
