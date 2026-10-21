import { useState, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { BookOpenCheck, Brain, MessageSquareQuote, Sparkles, Wrench } from 'lucide-react'
import { api } from '../api/client'
import type { IssueDetailT, Tag } from '../api/types'
import { engineRank, formatDate } from '../lib/format'
import { ISSUE_TYPE, TIER_ORDER, assetLabel, laneLabel } from '../lib/fixLabels'
import { ownerChip } from '../lib/owners'
import { TAG_CLASS } from './ClaimChip'
import EngineScorecard from './EngineScorecard'
import MomentCard from './MomentCard'
import FactTable from './FactTable'
import FixCard from './FixCard'
import { ErrorRetry } from './PageState'
import { useGeniePanel } from '../state/genie-panel'

type ClaimGroup = { key: string; engines: string[]; prompt_id: string; prompt_text: string; text: string | null; stated_value: string | null; tag: Tag }

function groupClaims(claims: IssueDetailT['said']['claims']): ClaimGroup[] {
  const out = new Map<string, ClaimGroup>()
  for (const c of claims) {
    const key = `${c.prompt_id}|${c.stated_value ?? ''}|${c.tag}`
    const g = out.get(key)
    if (g) { if (!g.engines.includes(c.engine)) g.engines.push(c.engine) } else out.set(key, { key, engines: [c.engine], ...c })
  }
  for (const g of out.values()) g.engines.sort((a, b) => engineRank(a) - engineRank(b))
  return [...out.values()]
}

function Block({ icon, title, children }: { icon: ReactNode; title: string; children: ReactNode }) {
  return (
    <section className="space-y-3 border-t border-gray-100 pt-5 first:border-t-0 first:pt-0">
      <h4 className="font-semibold flex items-center gap-2"><span className="text-lce-orange">{icon}</span>{title}</h4>
      {children}
    </section>
  )
}

function Fixes({ d }: { d: IssueDetailT }) {
  const fixes = [...d.fixes].sort((a, b) => (TIER_ORDER[a.tier] ?? 9) - (TIER_ORDER[b.tier] ?? 9))
  const [tab, setTab] = useState(fixes[0]?.fix_id)
  if (fixes.length === 0) return <p className="text-sm text-text-tertiary">No fix drafted for this issue yet.</p>
  const sel = fixes.find(f => f.fix_id === tab) ?? fixes[0]
  return (
    <div className="space-y-4">
      {fixes.length > 1 && (
        <div className="flex flex-wrap gap-1 bg-surface-secondary rounded-2xl p-1.5 w-fit">
          {fixes.map(f => (
            <button key={f.fix_id} type="button" onClick={() => setTab(f.fix_id)} className={`nav-item !py-1.5 !px-3 ${f.fix_id === sel.fix_id ? 'active' : ''}`}>
              {assetLabel(f.asset_type)}
            </button>
          ))}
        </div>
      )}
      <FixCard key={`${sel.fix_id}:${sel.state}`} fix={sel} facts={d.truth.facts} />
    </div>
  )
}

export default function IssueDetail({ issueId }: { issueId: string }) {
  const { data: d, isLoading, isError, refetch } = useQuery({ queryKey: ['issue', issueId], queryFn: () => api.issue(issueId) })
  const { ask } = useGeniePanel()

  if (isLoading) return <div className="card p-6 h-96 bg-gray-100 animate-pulse" />
  if (isError || !d) return <ErrorRetry message="Couldn't load this issue." onRetry={() => refetch()} />

  const { issue, said, truth } = d
  const t = ISSUE_TYPE[issue.issue_type]
  const groups = groupClaims(said.claims)

  return (
    <div className="card p-6 space-y-5">
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-2">
          <h3 className="font-semibold text-lg">{issue.title}</h3>
          <div className="flex flex-wrap items-center gap-2 text-xs">
            {t && <span className={`rounded-md px-1.5 py-0.5 font-medium ${t.cls}`}>{t.label}</span>}
            <span className="text-text-secondary">{laneLabel(issue.action_lane)}</span>
          </div>
        </div>
        <button type="button" className="btn btn-ghost !text-xs shrink-0" onClick={() => ask('Which engines and sources repeat this claim?')}>
          <Sparkles className="w-3.5 h-3.5" />Ask Genie about this issue
        </button>
      </div>

      <Block icon={<MessageSquareQuote className="w-4 h-4" />} title="What AI said">
        {groups.length > 0 && (
          <div className="space-y-2">
            {groups.map(g => (
              <div key={g.key} className="rounded-xl border border-gray-100 bg-surface-secondary p-3 space-y-1.5">
                <div className="flex flex-wrap items-center gap-1.5">
                  {g.engines.map(e => <span key={e} className="badge b-info">{e}</span>)}
                  <Link to={`/measure/prompts/${g.prompt_id}`} className="text-xs text-text-secondary hover:underline">{g.prompt_text}</Link>
                </div>
                <p className="text-sm flex flex-wrap items-center gap-2">
                  {g.text && <span>&ldquo;{g.text}&rdquo;</span>}
                  <span className={`inline-flex rounded-md px-2 py-0.5 text-[11px] font-medium ${TAG_CLASS[g.tag]}`}>{g.stated_value ?? 'claim'} · {g.tag}</span>
                </p>
              </div>
            ))}
          </div>
        )}
        {said.passage && (
          <figure className="rounded-xl border-l-4 border-amber-600 bg-amber-50 px-4 py-3 space-y-2">
            <blockquote className="text-sm italic">&ldquo;{said.passage.excerpt}&rdquo;</blockquote>
            <figcaption>
              <a href={said.passage.url} target="_blank" rel="noreferrer"
                className={`inline-flex rounded-md px-2 py-0.5 text-[11px] font-medium hover:underline ${ownerChip(said.passage.owner_class)}`}>
                {said.passage.domain} · {said.passage.owner_class} · last updated {formatDate(said.passage.last_updated)}
              </a>
            </figcaption>
          </figure>
        )}
        {said.memory && (
          <p className="flex items-center gap-2 text-sm text-text-secondary"><Brain className="w-4 h-4" />Answered from model memory: no source cited.</p>
        )}
        {said.moment && <MomentCard m={said.moment} />}
        {said.scorecards.map(s => (
          <div key={s.prompt_id} className="space-y-2">
            <Link to={`/measure/prompts/${s.prompt_id}`} className="text-sm font-medium hover:underline">{s.prompt_text}</Link>
            <EngineScorecard answers={s.answers} />
          </div>
        ))}
        {groups.length === 0 && !said.passage && !said.memory && !said.moment && said.scorecards.length === 0 && (
          <p className="text-sm text-text-tertiary">No engine answers recorded for this issue.</p>
        )}
      </Block>

      <Block icon={<BookOpenCheck className="w-4 h-4" />} title="What's true">
        <FactTable facts={truth.facts} ucTable={truth.uc_table} />
      </Block>

      <Block icon={<Wrench className="w-4 h-4" />} title="The fix">
        <Fixes key={issue.issue_id} d={d} />
      </Block>
    </div>
  )
}
