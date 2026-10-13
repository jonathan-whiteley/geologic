import { useEffect, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Wand2, Check, X, ShieldCheck, AlertCircle } from 'lucide-react'
import { api } from '../api/client'
import type { PublishStatus, Suggestion } from '../api/types'
import { useToast } from './Toast'

const FAILED = 'Publish failed. Try again.'
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

export default function DraftPanel({ suggestions }: { suggestions: Suggestion[] }) {
  const toast = useToast()
  const queryClient = useQueryClient()
  const [selectedId, setSelectedId] = useState<string | null>(
    () => (suggestions.find(x => x.state === 'pending_review') ?? suggestions[0])?.suggestion_id ?? null,
  )
  const [overlay, setOverlay] = useState<Record<string, PublishStatus>>({})
  const [publishingId, setPublishingId] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [approving, setApproving] = useState(false)
  const [rejecting, setRejecting] = useState(false)

  useEffect(() => {
    if (!publishingId) return
    let stopped = false
    let timer: number
    const tick = async () => {
      if (stopped) return
      try {
        const st = await api.status(publishingId)
        setOverlay(prev => ({ ...prev, [publishingId]: st }))
        // Stop on anything other than an in-flight publish: published, blocked, or a failure the job
        // returned to pending_review (Approve is clickable again).
        if (st.state !== 'publishing' || st.error) {
          setPublishingId(null)
          if (st.state === 'published') {
            // The status poll saved the proof row server-side; refresh Prove and the review badge.
            queryClient.invalidateQueries({ queryKey: ['impact'] })
            queryClient.invalidateQueries({ queryKey: ['suggestions'] })
          } else if (st.state !== 'blocked') {
            setOverlay(prev => ({ ...prev, [publishingId]: { ...st, error: st.error || FAILED } }))
            queryClient.invalidateQueries({ queryKey: ['suggestions'] })
          }
          return
        }
      } catch {
        // transient polling error; keep trying
      }
      if (!stopped) timer = window.setTimeout(tick, 2000)
    }
    timer = window.setTimeout(tick, 2000)
    return () => { stopped = true; window.clearTimeout(timer) }
  }, [publishingId, queryClient])

  const selected = suggestions.find(x => x.suggestion_id === selectedId) ?? suggestions[0]
  if (!selected) return null
  const s = merge(selected, overlay[selected.suggestion_id])

  async function handleApprove() {
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
    setActionError(null)
    setRejecting(true)
    try {
      await api.reject(selected.suggestion_id)
      await queryClient.invalidateQueries({ queryKey: ['suggestions'] })
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Something went wrong.')
    } finally {
      setRejecting(false)
    }
  }

  const diff = diffLines(s.diff_before, s.diff_after)
  const addedCount = diff.after.filter(l => l.add).length

  return (
    <div className="space-y-5">
      {suggestions.length > 1 && (
        <div className="flex flex-wrap gap-1.5">
          {suggestions.map(item => (
            <button
              key={item.suggestion_id}
              onClick={() => setSelectedId(item.suggestion_id)}
              className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-colors ${item.suggestion_id === s.suggestion_id ? 'bg-lce-orange/5 ring-1 ring-lce-orange/30' : 'bg-surface-secondary text-text-secondary hover:bg-gray-100'}`}
            >
              {item.tier} · {item.asset_type}
            </button>
          ))}
        </div>
      )}

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

      <p className="text-sm text-text-secondary">{s.rationale}</p>

      <div className="grid md:grid-cols-2 gap-4">
        <div>
          <p className="text-xs font-medium text-text-secondary mb-2">Current page</p>
          {s.diff_before === null ? (
            <div className="code">(no existing content)</div>
          ) : (
            <div className="code">
              {diff.before.map((l, i) => l.del ? <span key={i} className="del">{l.text}</span> : <span key={i}>{l.text}{'\n'}</span>)}
            </div>
          )}
        </div>
        <div>
          <p className="text-xs font-medium text-text-secondary mb-2 flex items-center gap-2">
            Proposed
            {addedCount > 0 && <span className="badge b-success">+{addedCount} lines</span>}
          </p>
          <div className="code">
            {diff.after.map((l, i) => l.add ? <span key={i} className="add">{l.text}</span> : <span key={i}>{l.text}{'\n'}</span>)}
          </div>
        </div>
      </div>

      {s.checks.length > 0 && (
        <div>
          <p className="text-xs font-medium text-text-secondary mb-2 flex items-center gap-1.5">
            <ShieldCheck className="w-3.5 h-3.5" />
            Brand Guardian
          </p>
          <ul className="space-y-1.5 text-sm">
            {s.checks.map((c, i) => (
              <li key={i} className="flex items-start gap-2">
                <span className={`w-4 h-4 mt-0.5 rounded-full flex items-center justify-center shrink-0 ${c.ok ? 'bg-green-50 text-green-600' : 'bg-amber-50 text-amber-600'}`}>
                  {c.ok ? <Check className="w-3 h-3" /> : <AlertCircle className="w-3 h-3" />}
                </span>
                {c.label}
              </li>
            ))}
          </ul>
        </div>
      )}

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

      {overlay[s.suggestion_id] && s.state !== 'pending_review' && (
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
              parts.push(`Share of Model ${sum.share_before.toFixed(2)} → ${sum.share_after.toFixed(2)}.`)
            }
            return parts.length ? <p className="text-sm text-text-secondary">{parts.join(' ')}</p> : null
          })()}
        </div>
      )}

      {actionError && <p className="text-sm text-red-600">{actionError}</p>}
    </div>
  )
}
