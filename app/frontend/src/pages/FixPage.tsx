import { useEffect, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import type { FixStatus } from '../api/types'
import { CLUSTERS } from '../components/Heatmap'
import TierStrip from '../components/TierStrip'
import QuarantineTrail from '../components/QuarantineTrail'
import IssueQueue, { filterIssues, type QueueFilter } from '../components/IssueQueue'
import IssueDetail from '../components/IssueDetail'
import PublishProgress from '../components/PublishProgress'
import { PageSkeleton, ErrorRetry } from '../components/PageState'
import { useToast } from '../components/Toast'
import { useGeniePanel } from '../state/genie-panel'

const CLUSTER_LABEL = new Map(CLUSTERS)

export default function FixPage() {
  const [params, setParams] = useSearchParams()
  const cluster = params.get('cluster')
  const issueParam = params.get('issue')
  const [filter, setFilter] = useState<QueueFilter>('all')
  const [showTrail, setShowTrail] = useState(false)
  const [t0Ids, setT0Ids] = useState<string[]>([])
  const [t0Running, setT0Running] = useState<string[]>([])
  const [t0Starting, setT0Starting] = useState(false)
  const toast = useToast()
  const queryClient = useQueryClient()
  const { setFocus } = useGeniePanel()

  const summary = useQuery({ queryKey: ['fix-summary'], queryFn: api.fixSummary })
  const issues = useQuery({ queryKey: ['issues', cluster], queryFn: () => api.issues(cluster ? { cluster } : undefined) })

  const rows = issues.data ?? []
  const visible = filterIssues(rows, filter)
  const sel = rows.find(r => r.issue_id === issueParam) ?? visible[0]

  useEffect(() => {
    setFocus(sel?.title ?? null)
    return () => setFocus(null)
  }, [sel?.title, setFocus])

  function update(next: Record<string, string | null>) {
    const p = new URLSearchParams(params)
    for (const [k, v] of Object.entries(next)) { if (v === null) p.delete(k); else p.set(k, v) }
    setParams(p, { replace: true })
  }

  async function approveT0() {
    setT0Starting(true)
    try {
      const { fix_ids } = await api.approveT0()
      toast(`Publishing ${fix_ids.length} T0 fixes`)
      setT0Ids(fix_ids)
      setT0Running(fix_ids)
      queryClient.invalidateQueries({ queryKey: ['fix-summary'] })
      queryClient.invalidateQueries({ queryKey: ['fixes'] })
    } catch (err) {
      toast(err instanceof Error ? err.message : "Couldn't start publishing. Try again.")
    } finally {
      setT0Starting(false)
    }
  }

  // A published T0 card clears after 4 s; a failed one stays so its error remains visible.
  const endT0 = (id: string, st: FixStatus) => {
    setT0Running(ids => ids.filter(x => x !== id))
    if (st.state === 'published') window.setTimeout(() => setT0Ids(ids => ids.filter(x => x !== id)), 4000)
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <p className="text-xs font-semibold uppercase tracking-wider text-lce-orange-dark mb-1">Fix</p>
        <h2 className="text-2xl font-semibold">Which sources are wrong, out of date, or leave us out</h2>
        <p className="text-text-secondary">Every fix is grounded in Unity Catalog facts and approved in Lakebase. Then we re-ask the engines.</p>
      </div>

      <TierStrip summary={summary.data} t0Busy={t0Starting || t0Running.length > 0} onApproveT0={approveT0} onOpenQuarantine={() => setShowTrail(true)} />

      {t0Ids.length > 0 && (
        <div className="card p-5 space-y-3">
          <p className="text-sm font-semibold">Publishing T0 fixes</p>
          <div className="grid md:grid-cols-2 gap-4">
            {t0Ids.map(id => <PublishProgress key={id} fixId={id} fresh onEnd={st => endT0(id, st)} />)}
          </div>
        </div>
      )}

      {issues.isLoading ? (
        <PageSkeleton statCards={0} />
      ) : issues.isError ? (
        <ErrorRetry message="Couldn't load the issue queue." onRetry={() => issues.refetch()} />
      ) : (
        <div className="grid lg:grid-cols-[minmax(320px,5fr)_7fr] gap-6 items-start">
          <IssueQueue
            rows={rows}
            filter={filter}
            onFilter={setFilter}
            selectedId={sel?.issue_id}
            onSelect={id => update({ issue: id })}
            clusterLabel={cluster ? (CLUSTER_LABEL.get(cluster) ?? cluster) : null}
            onClearCluster={() => update({ cluster: null })}
          />
          {sel ? <IssueDetail issueId={sel.issue_id} /> : <div className="card p-6 text-sm text-text-tertiary text-center">No issues yet.</div>}
        </div>
      )}

      {showTrail && <QuarantineTrail onClose={() => setShowTrail(false)} />}
    </div>
  )
}
