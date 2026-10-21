import { useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Check, Circle, Loader2 } from 'lucide-react'
import { api } from '../api/client'
import type { FixStatus } from '../api/types'
import { formatTime } from '../lib/format'
import LedgerMini from './LedgerMini'

const FALLBACK_S = 90

function stepState(i: number, st: FixStatus): 'done' | 'running' | 'pending' {
  if (st.state === 'published' || st.state === 'approved') return 'done'
  if (st.publish_step > i) return 'done'
  if (st.publish_step === i && st.state === 'publishing') return 'running'
  return 'pending'
}

const MAX_404 = 3
const FAILED = 'Publish failed. Try again.'

/** Polls a fix's publish status every 2 s and shows the five steps, then the before → after (or the rehearsed fallback).
 *  `fresh` means this client started the run, so its end refreshes the screens even if the poll never saw `publishing`. */
export default function PublishProgress({ fixId, onEnd, fresh = false }: { fixId: string; onEnd?: (st: FixStatus) => void; fresh?: boolean }) {
  const queryClient = useQueryClient()
  const [st, setSt] = useState<FixStatus | null>(null)
  const [local, setLocal] = useState(0)
  const [pollError, setPollError] = useState(false)
  const [lost, setLost] = useState(false)
  const onEndRef = useRef(onEnd)
  onEndRef.current = onEnd
  const freshRef = useRef(fresh)
  freshRef.current = fresh

  useEffect(() => {
    const t = window.setInterval(() => setLocal(s => s + 1), 1000)
    return () => window.clearInterval(t)
  }, [fixId])

  useEffect(() => {
    let stopped = false
    let timer: number
    let sawPublishing = false
    let misses = 0
    const tick = async () => {
      try {
        const s = await api.fixStatus(fixId)
        if (stopped) return
        setSt(s)
        setPollError(false)
        misses = 0
        if (s.state === 'publishing') sawPublishing = true
        else {
          // Only a run that was live (seen publishing, or started here) refreshes the screens; mounting on a finished fix does not.
          if (sawPublishing || freshRef.current) {
            for (const key of ['fixes', 'issues', 'issue', 'fix-summary', 'impact']) queryClient.invalidateQueries({ queryKey: [key] })
          }
          onEndRef.current?.(s)
          return
        }
      } catch (err) {
        if (stopped) return
        setPollError(true)
        if ((err as { status?: number }).status === 404 && ++misses >= MAX_404) {
          setLost(true)
          return
        }
      }
      if (!stopped) timer = window.setTimeout(tick, 2000)
    }
    void tick()
    return () => { stopped = true; window.clearTimeout(timer) }
  }, [fixId, queryClient])

  if (lost) return <p className="text-sm text-red-600">Lost contact with the server.</p>
  if (!st) return <p className="flex items-center gap-2 text-sm text-text-secondary"><Loader2 className="w-4 h-4 animate-spin" />Starting...</p>

  const elapsed = st.state === 'publishing' ? Math.max(st.elapsed_s ?? 0, local) : (st.elapsed_s ?? local)
  const live = st.state === 'publishing'

  return (
    <div className="space-y-3">
      {(live || st.state === 'published') && (
        <div className="rounded-xl border border-gray-100 bg-surface-secondary p-4 space-y-2">
          <div className="flex items-center justify-between text-xs text-text-tertiary">
            <span>{live ? 'Publishing' : 'Published'}</span>
            <span className="tabular-nums">{elapsed}s</span>
          </div>
          <ol className="space-y-1.5">
            {st.step_labels.map((label, i) => {
              const s = stepState(i, st)
              return (
                <li key={label} className={`flex items-center gap-2 text-sm ${s === 'pending' ? 'text-text-tertiary' : ''}`}>
                  {s === 'done' ? <Check className="w-4 h-4 text-green-600" /> : s === 'running' ? <Loader2 className="w-4 h-4 animate-spin text-lce-orange" /> : <Circle className="w-4 h-4" />}
                  {label}
                </li>
              )
            })}
          </ol>
          {pollError && live && <p className="text-xs text-amber-700">Lost contact with the server. Retrying...</p>}
        </div>
      )}

      {st.state === 'published' && (st.entry ? <LedgerMini entry={st.entry} /> : <p className="text-sm font-medium text-green-700">Published</p>)}
      {st.state === 'approved' && <p className="text-sm font-medium text-green-700">Approved. Ready for a human to send.</p>}
      {live && st.fallback && (
        <LedgerMini entry={st.fallback.entry} label={`Rehearsed at ${formatTime(st.fallback.rehearsed_at)}`} note="The live re-ask is still running." />
      )}
      {live && !st.fallback && (st.elapsed_s ?? 0) > FALLBACK_S && (
        <p className="flex items-center gap-2 text-sm text-text-secondary"><Loader2 className="w-4 h-4 animate-spin" />Still re-asking the engines...</p>
      )}
      {st.state === 'pending_review' && <p className="text-sm text-red-600">{st.error ?? FAILED}</p>}
      {st.state === 'rejected' && <p className="text-sm text-text-tertiary">Rejected.</p>}
      {st.state === 'blocked' && <p className="text-sm text-red-600">{st.error ?? 'Blocked by policy.'}</p>}
    </div>
  )
}
