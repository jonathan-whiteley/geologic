import { useQuery } from '@tanstack/react-query'
import { BadgeCheck, Eye, Grid3x3, Link as LinkIcon, Link2, PieChart, ShieldCheck } from 'lucide-react'
import { api } from '../api/client'
import type { BrandRow } from '../api/types'
import { formatTime, fx } from '../lib/format'
import { ownerClass } from '../lib/owners'
import Heatmap from '../components/Heatmap'
import KpiCard from '../components/KpiCard'
import AskAnything from '../components/AskAnything'
import PromptTable from '../components/PromptTable'
import SuggestedPrompts from '../components/SuggestedPrompts'
import SourceTypeBar from '../components/SourceTypeBar'
import { PageSkeleton, ErrorRetry } from '../components/PageState'

const isLce = (b: BrandRow) => b.brand.toLowerCase().includes('caesar')

export default function MeasurePage() {
  const summary = useQuery({ queryKey: ['model'], queryFn: api.modelSummary })
  const prompts = useQuery({ queryKey: ['prompts'], queryFn: api.prompts })

  if (summary.isLoading) return <PageSkeleton />
  if (summary.isError || !summary.data) return <ErrorRetry message="Couldn't load Measure." onRetry={() => summary.refetch()} />

  const { kpis, brands, heatmap, source_types, top_domains, gateway } = summary.data
  const expected = kpis.tracked_prompts * kpis.engines
  const competitors = brands.filter(b => !isLce(b))

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

      <div className="card p-2 grid sm:grid-cols-2 lg:grid-cols-4 gap-1">
        {brands.map(b => {
          const us = isLce(b)
          return (
            <div key={b.brand} className={`flex items-center gap-3 rounded-xl px-3 py-2.5 ${us ? 'bg-lce-orange/5 ring-1 ring-lce-orange/30' : ''}`}>
              <span className="w-9 h-9 rounded-lg bg-surface border border-gray-100 flex items-center justify-center overflow-hidden shrink-0">
                <img src={b.logo} alt="" className="max-w-[28px] max-h-[28px] object-contain" />
              </span>
              <div className="min-w-0">
                <p className="text-sm font-medium flex items-center gap-2 whitespace-nowrap">
                  {b.brand}
                  {us && <span className="text-[11px] font-semibold px-1.5 py-0.5 rounded-md border border-lce-orange/30 bg-lce-cream text-lce-orange-dark">Your brand</span>}
                </p>
                <p className="text-xs text-text-secondary tabular-nums">
                  Share of Model <b className="text-text-primary">{fx(b.answer_share)}</b> · Position {fx(b.avg_position, 1)}
                </p>
              </div>
            </div>
          )
        })}
      </div>

      <AskAnything />

      {prompts.isError ? (
        <ErrorRetry message="Couldn't load the tracked prompts." onRetry={() => prompts.refetch()} />
      ) : prompts.data ? (
        <PromptTable rows={prompts.data} />
      ) : (
        <div className="card p-6 h-64 bg-gray-100 animate-pulse" />
      )}

      <SuggestedPrompts />

      <div className="grid lg:grid-cols-2 gap-6">
        <div className="card p-6 space-y-5">
          <div className="flex items-center gap-3">
            <div className="icon-tile"><Link2 className="w-5 h-5" /></div>
            <div>
              <h3 className="font-semibold">Where answers come from</h3>
              <p className="text-sm text-text-secondary">Citations by source type</p>
            </div>
          </div>
          <SourceTypeBar data={source_types} />
          <div>
            <p className="text-sm font-semibold mb-2">Top unowned domains</p>
            <div className="divide-y divide-gray-100">
              {top_domains.map(d => (
                <div key={d.domain} className="flex items-center gap-3 py-2 text-sm">
                  <span className="font-mono flex-1 truncate">{d.domain}</span>
                  <span className={`badge ${ownerClass(d.owner_class)}`}>{d.owner_class}</span>
                  <span className="tabular-nums text-text-secondary w-24 text-right">{d.citations} citations</span>
                  <span className="tabular-nums text-text-secondary w-20 text-right">{d.prompts} prompts</span>
                </div>
              ))}
              {top_domains.length === 0 && <p className="text-sm text-text-tertiary py-2">No unowned citations.</p>}
            </div>
          </div>
        </div>

        <div className="card p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="icon-tile"><Grid3x3 className="w-5 h-5" /></div>
            <div>
              <h3 className="font-semibold">Share of Model by cluster and engine</h3>
              <p className="text-sm text-text-secondary">Unbranded tracked prompts</p>
            </div>
          </div>
          <div className="overflow-x-auto">
            <Heatmap data={heatmap} />
          </div>
        </div>
      </div>
    </div>
  )
}
