import { useEffect, useMemo, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { Wand2, GitBranch, Check, X, ShieldCheck, AlertCircle } from 'lucide-react'
import { api } from '../api/client'
import type { PublishStatus, Suggestion } from '../api/types'
import { PageSkeleton, ErrorRetry } from '../components/PageState'
import { useToast } from '../components/Toast'

const STEP_NAMES = ['Brand Guardian re-check', 'Publish to CMS', 'Vector index sync', 'Re-probe questions', 'Judge answers']

function stepState(i: number, publishStep: number): 'done' | 'running' | 'pending' {
  if (publishStep > i) return 'done'
  if (i === publishStep) return 'running'
  if (publishStep === 3 && i === 4) return 'running'
  return 'pending'
}

function diffLines(before: string | null, after: string) {
  const beforeLines = (before ?? '').split('\n')
  const afterLines = after.split('\n')
  const beforeSet = new Set(beforeLines)
  const afterSet = new Set(afterLines)
  return {
    before: beforeLines.map(text => ({ text, del: !afterSet.has(text) })),
    after: afterLines.map(text => ({ text, add: !beforeSet.has(text) })),
  }
}

function merge(s: Suggestion, overlay?: PublishStatus): Suggestion & { statusExtra?: PublishStatus } {
  if (!overlay) return s
  return { ...s, state: overlay.state, publish_step: overlay.publish_step, error: overlay.error, statusExtra: overlay }
}

const traceHref = (traceId: string) =>
  `/ml/experiments/search?searchFilter=${encodeURIComponent("name = '/Shared/geologic-drafting'")}#trace=${encodeURIComponent(traceId)}`

export default function ActPage() {
  const toast = useToast()
  const [searchParams] = useSearchParams()
  const oppParam = searchParams.get('opp')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [overlay, setOverlay] = useState<Record<string, PublishStatus>>({})
  const [publishingId, setPublishingId] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [approving, setApproving] = useState(false)
  const [rejecting, setRejecting] = useState(false)
  const initialized = useRef(false)

  const { data, isLoading, isError, refetch } = useQuery({ queryKey: ['suggestions'], queryFn: api.suggestions })

  const queue = useMemo(() => {
    if (!data) return []
    const rank = (s: Suggestion) => (merge(s, overlay[s.suggestion_id]).state === 'pending_review' ? 0 : 1)
    return [...data].sort((a, b) => rank(a) - rank(b))
  }, [data, overlay])

  useEffect(() => {
    if (initialized.current || !data || data.length === 0) return
    initialized.current = true
    const byOpp = oppParam ? data.find(s => s.opp_id === oppParam) : null
    setSelectedId((byOpp ?? queue[0])?.suggestion_id ?? null)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data])

  useEffect(() => {
    if (!publishingId) return
    let stopped = false
    let timer: number
    const tick = async () => {
      if (stopped) return
      try {
        const st = await api.status(publishingId)
        setOverlay(prev => ({ ...prev, [publishingId]: st }))
        if (st.state === 'published' || st.state === 'blocked' || st.state === 'error') {
          setPublishingId(null)
          return
        }
      } catch {
        // transient polling error; keep trying
      }
      if (!stopped) timer = window.setTimeout(tick, 2000)
    }
    timer = window.setTimeout(tick, 2000)
    return () => { stopped = true; window.clearTimeout(timer) }
  }, [publishingId])

  if (isLoading) return <PageSkeleton statCards={0} />
  if (isError || !data) return <ErrorRetry message="Couldn't load the review queue." onRetry={() => refetch()} />

  const selected = queue.find(s => s.suggestion_id === selectedId) ?? queue[0]
  const s = selected ? merge(selected, overlay[selected.suggestion_id]) : null

  async function handleApprove() {
    if (!selected) return
    setActionError(null)
    setApproving(true)
    try {
      await api.approve(selected.suggestion_id)
      setOverlay(prev => ({ ...prev, [selected.suggestion_id]: { state: 'publishing', publish_step: 0, error: null } }))
      setPublishingId(selected.suggestion_id)
    } catch (err) {
      const status = (err as { status?: number }).status
      const message = err instanceof Error ? err.message : 'Something went wrong.'
      if (status === 409) toast(message)
      else setActionError(message)
    } finally {
      setApproving(false)
    }
  }

  async function handleReject() {
    if (!selected) return
    setActionError(null)
    setRejecting(true)
    try {
      await api.reject(selected.suggestion_id)
      await refetch()
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Something went wrong.')
    } finally {
      setRejecting(false)
    }
  }

  const diff = s ? diffLines(s.diff_before, s.diff_after) : null
  const addedCount = diff?.after.filter(l => l.add).length ?? 0

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <p className="text-xs font-semibold uppercase tracking-wider text-lce-orange-dark mb-1">Act</p>
        <h2 className="text-2xl font-semibold">Review Studio</h2>
        <p className="text-text-secondary">Agent-drafted content changes, tiered by risk. T0 publishes automatically; T1 and T2 need you.</p>
      </div>

      {!s ? (
        <div className="card p-6 text-sm text-text-tertiary text-center">Nothing in the review queue yet.</div>
      ) : (
        <div className="grid lg:grid-cols-3 gap-6">
          <div className="card p-6 lg:col-span-2 space-y-5">
            <div className="flex items-start justify-between gap-4 flex-wrap">
              <div className="flex items-center gap-3">
                <div className="icon-tile"><Wand2 className="w-5 h-5" /></div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className={`tier ${s.tier.toLowerCase()}`}>{s.tier}</span>
                    <span className="text-sm text-text-secondary">{s.asset_type}</span>
                  </div>
                  <h3 className="font-semibold text-lg">{s.title}</h3>
                </div>
              </div>
              {s.agent_trace_id && (
                <a href={traceHref(s.agent_trace_id)} target="_blank" rel="noreferrer" className="btn btn-ghost !px-2 !py-1 text-blue-700">
                  <GitBranch className="w-4 h-4" />
                  Agent trace
                </a>
              )}
            </div>

            <p className="text-sm text-text-secondary">{s.rationale}</p>

            <div className="grid md:grid-cols-2 gap-4">
              <div>
                <p className="text-xs font-medium text-text-secondary mb-2">Current page</p>
                {s.diff_before === null ? (
                  <div className="code">(no existing content)</div>
                ) : (
                  <div className="code">
                    {diff!.before.map((l, i) => l.del ? <span key={i} className="del">{l.text}</span> : <span key={i}>{l.text}{'\n'}</span>)}
                  </div>
                )}
              </div>
              <div>
                <p className="text-xs font-medium text-text-secondary mb-2 flex items-center gap-2">
                  Proposed
                  {addedCount > 0 && <span className="badge b-success">+{addedCount} lines</span>}
                </p>
                <div className="code">
                  {diff!.after.map((l, i) => l.add ? <span key={i} className="add">{l.text}</span> : <span key={i}>{l.text}{'\n'}</span>)}
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2 flex-wrap">
              {s.tier === 'T0' ? (
                <button className="btn btn-primary" disabled>
                  <Check className="w-4 h-4" />
                  Published automatically
                </button>
              ) : s.state === 'pending_review' ? (
                <>
                  <button className="btn btn-primary" onClick={handleApprove} disabled={approving}>
                    <Check className="w-4 h-4" />
                    {s.tier === 'T2' ? 'Approve association' : 'Approve and publish'}
                  </button>
                  <button className="btn btn-ghost text-red-600" onClick={handleReject} disabled={rejecting}>
                    <X className="w-4 h-4" />
                    Reject
                  </button>
                </>
              ) : (
                <span className="badge b-default">{s.state.replace('_', ' ')}</span>
              )}
            </div>

            {s.error && <p className="text-sm text-red-600">{s.error}</p>}

            {overlay[s.suggestion_id] && (
              <div className="rounded-xl border border-gray-100 bg-surface-secondary p-4 space-y-4">
                <div className="flex flex-wrap gap-2 text-xs">
                  {STEP_NAMES.map((name, i) => {
                    const st = stepState(i, s.publish_step)
                    return (
                      <span key={name} className={`badge ${st === 'done' ? 'b-success' : st === 'running' ? 'b-brand animate-pulse-soft' : 'b-default'}`}>
                        <span className="dot" />{name}
                      </span>
                    )
                  })}
                </div>

                {s.state === 'published' && s.statusExtra?.before && s.statusExtra?.after && (() => {
                  const before = s.statusExtra!.before!
                  const after = s.statusExtra!.after!
                  return (
                    <div className="grid md:grid-cols-2 gap-4">
                      <div className="bg-white rounded-xl border border-gray-100 p-4 space-y-2">
                        <span className="badge b-default">Before · Claude</span>
                        <p className="text-sm">{before.answer}</p>
                        <p className="font-mono text-[11px] text-text-tertiary">cites: {before.cited.join(' · ') || 'none'}</p>
                      </div>
                      <div className="bg-white rounded-xl border border-green-100 p-4 space-y-2 shadow-soft">
                        <span className="badge b-success"><span className="dot" />After · Claude</span>
                        <p className="text-sm">{after.answer}</p>
                        <p className="font-mono text-[11px] text-lce-orange-dark">cites: {after.cited.join(' · ') || 'none'}</p>
                      </div>
                    </div>
                  )
                })()}

                {s.state === 'published' && s.statusExtra?.summary && (() => {
                  const sum = s.statusExtra!.summary!
                  const parts: string[] = []
                  if (sum.accuracy_before !== null && sum.accuracy_after !== null) {
                    parts.push(`Accuracy ${sum.accuracy_before.toFixed(0)}% → ${sum.accuracy_after.toFixed(0)}%.`)
                  }
                  if (sum.share_before !== null && sum.share_after !== null) {
                    parts.push(`Answer Share ${sum.share_before.toFixed(2)} → ${sum.share_after.toFixed(2)}.`)
                  }
                  return parts.length ? <p className="text-sm text-text-secondary">{parts.join(' ')}</p> : null
                })()}
              </div>
            )}

            {actionError && <p className="text-sm text-red-600">{actionError}</p>}
          </div>

          <div className="space-y-6">
            <div className="card p-4">
              <h3 className="font-semibold px-2 pb-2">Review queue</h3>
              <div className="space-y-1">
                {queue.map(item => {
                  const m = merge(item, overlay[item.suggestion_id])
                  const isSelected = item.suggestion_id === s.suggestion_id
                  return (
                    <button
                      key={item.suggestion_id}
                      onClick={() => setSelectedId(item.suggestion_id)}
                      className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-left transition-colors ${isSelected ? 'bg-lce-orange/5 ring-1 ring-lce-orange/30' : 'hover:bg-gray-50'}`}
                    >
                      <span className={`tier ${item.tier.toLowerCase()}`}>{item.tier}</span>
                      <span className="min-w-0">
                        <span className="block text-sm font-medium truncate">{item.title}</span>
                        <span className="block text-xs text-text-secondary">
                          {item.asset_type}{m.state !== 'pending_review' ? ` · ${m.state.replace('_', ' ')}` : ''}
                        </span>
                      </span>
                    </button>
                  )
                })}
              </div>
            </div>

            <div className="card p-6">
              <div className="flex items-center gap-3 mb-4">
                <div className="icon-tile"><ShieldCheck className="w-5 h-5" /></div>
                <h3 className="font-semibold">Brand Guardian</h3>
              </div>
              <ul className="space-y-2.5 text-sm">
                {s.checks.map((c, i) => (
                  <li key={i} className="flex items-start gap-2.5">
                    <span className={`w-5 h-5 rounded-full flex items-center justify-center shrink-0 ${c.ok ? 'bg-green-50 text-green-600' : 'bg-amber-50 text-amber-600'}`}>
                      {c.ok ? <Check className="w-3.5 h-3.5" /> : <AlertCircle className="w-3.5 h-3.5" />}
                    </span>
                    {c.label}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
