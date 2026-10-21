import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Check, Pencil, ThumbsUp, X } from 'lucide-react'
import { api } from '../api/client'
import type { FactRow, Fix, FixStatus } from '../api/types'
import { BLOCKING_CHECKS, MESSAGE_ASSETS, laneLabel, tierClass } from '../lib/fixLabels'
import { useToast } from './Toast'
import SectionDiff from './SectionDiff'
import PublishProgress from './PublishProgress'

const IN_FLIGHT = ['publishing', 'published', 'approved']

export default function FixCard({ fix: initial, facts }: { fix: Fix; facts: FactRow[] }) {
  const queryClient = useQueryClient()
  const toast = useToast()
  const [edited, setEdited] = useState<Fix | null>(null)
  const [started, setStarted] = useState(false)
  const [draft, setDraft] = useState(initial.patch_text)
  // Server state wins: drop a local edit (and a finished local run) when the server's state or patch text changes.
  const [seen, setSeen] = useState({ state: initial.state, patch: initial.patch_text })
  if (seen.state !== initial.state || seen.patch !== initial.patch_text) {
    setSeen({ state: initial.state, patch: initial.patch_text })
    setEdited(null)
    setDraft(initial.patch_text)
    if (initial.state === 'pending_review') setStarted(false)
  }
  const fix = edited ?? initial
  const progress = started || IN_FLIGHT.includes(fix.state)
  const [error, setError] = useState<string | null>(initial.state === 'pending_review' ? initial.error : null)
  const [busy, setBusy] = useState<'approve' | 'reject' | 'save' | null>(null)
  const [editing, setEditing] = useState(false)

  const factById = new Map(facts.map(f => [f.fact_id, f]))
  const blocked = fix.checks.some(c => !c.ok && BLOCKING_CHECKS.has(c.key))
  const reviewable = fix.state === 'pending_review' && !progress

  const refresh = () => { for (const key of ['fixes', 'issues', 'issue', 'fix-summary']) queryClient.invalidateQueries({ queryKey: [key] }) }

  async function approve() {
    setBusy('approve'); setError(null)
    try {
      await api.approve(fix.fix_id)
      setStarted(true)
      queryClient.invalidateQueries({ queryKey: ['fixes'] })
    } catch (err) {
      // 409: already publishing or no longer reviewable; follow the real state instead of guessing.
      if ((err as { status?: number }).status === 409) setStarted(true)
      else setError(err instanceof Error ? err.message : 'Publish failed. Try again.')
    } finally {
      setBusy(null)
    }
  }

  async function reject() {
    setBusy('reject'); setError(null)
    try {
      await api.reject(fix.fix_id)
      toast('Fix rejected')
      refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong.')
    } finally {
      setBusy(null)
    }
  }

  async function save() {
    setBusy('save'); setError(null)
    try {
      const updated = await api.edit(fix.fix_id, draft)
      setEdited(updated)
      setDraft(updated.patch_text)
      setEditing(false)
      refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong.')
    } finally {
      setBusy(null)
    }
  }

  function onEnd(st: FixStatus) {
    if (st.state === 'pending_review') {
      setStarted(false)
      setError(st.error ?? 'Publish failed. Try again.')
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-start gap-3 flex-wrap">
        <span className={`tier ${tierClass(fix.tier)}`}>{fix.tier}</span>
        <div className="flex-1 min-w-0">
          <p className="font-semibold">{fix.title}</p>
          <p className="text-xs text-text-secondary">
            {laneLabel(fix.lane)}
            {MESSAGE_ASSETS.has(fix.asset_type) && fix.recipient && <> · To: {fix.recipient}</>}
          </p>
          {fix.tier === 'T0' && <p className="text-xs text-text-tertiary mt-0.5">Would auto-publish in production</p>}
        </div>
      </div>

      {editing ? (
        <div className="space-y-2">
          <textarea aria-label="Edit the fix" className="w-full min-h-[160px] rounded-xl border border-gray-200 bg-surface p-3 font-mono text-xs focus:border-lce-orange"
            value={draft} onChange={e => setDraft(e.target.value)} />
          <div className="flex gap-2">
            <button type="button" className="btn btn-primary" onClick={save} disabled={busy !== null || !draft.trim()}>Save and re-check</button>
            <button type="button" className="btn btn-ghost" onClick={() => { setEditing(false); setDraft(fix.patch_text) }}>Cancel</button>
          </div>
        </div>
      ) : (
        <SectionDiff fix={fix} />
      )}

      {fix.grounding_fact_ids.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5 text-xs">
          <span className="text-text-secondary font-medium">Grounded in:</span>
          {fix.grounding_fact_ids.map(id => {
            const f = factById.get(id)
            return (
              <span key={id} className="font-mono font-semibold px-1.5 py-0.5 rounded-md bg-green-50 text-green-700"
                title={f ? `${f.subject_name} ${f.attribute.replace(/_/g, ' ')}: ${f.value}` : id}>{id}</span>
            )
          })}
        </div>
      )}

      {fix.sentences.length > 0 && (
        <ul className="space-y-1 text-xs">
          {fix.sentences.map((s, i) => (
            <li key={i} className="flex flex-wrap items-baseline gap-1.5">
              <span className="text-text-secondary">{s.text}</span>
              {s.kind === 'copy'
                ? <span className="px-1.5 rounded bg-gray-100 text-text-tertiary">copy, no facts</span>
                : s.fact_ids.map(id => <span key={id} className="font-mono px-1 rounded bg-green-50 text-green-700">{id}</span>)}
            </li>
          ))}
        </ul>
      )}

      {fix.checks.length > 0 && (
        <ul className="space-y-1">
          {fix.checks.map(c => (
            <li key={c.key} className={`flex items-center gap-2 text-sm ${c.ok ? '' : 'text-red-700'}`}>
              {c.ok ? <Check className="w-4 h-4 text-green-600 shrink-0" /> : <X className="w-4 h-4 text-red-600 shrink-0" />}
              {c.label}
            </li>
          ))}
        </ul>
      )}

      {progress ? (
        <PublishProgress fixId={fix.fix_id} onEnd={onEnd} fresh={started} />
      ) : reviewable && !editing ? (
        <div className="space-y-2">
          <div className="flex flex-wrap gap-2">
            <button type="button" className="btn btn-primary" onClick={approve} disabled={blocked || busy !== null}>
              <ThumbsUp className="w-4 h-4" />Approve
            </button>
            <button type="button" className="btn btn-secondary" onClick={() => setEditing(true)} disabled={busy !== null}>
              <Pencil className="w-4 h-4" />Edit
            </button>
            <button type="button" className="btn btn-ghost" onClick={reject} disabled={busy !== null}>Reject</button>
          </div>
          {blocked && <p className="text-xs text-red-600">Fix the failed checks to approve</p>}
        </div>
      ) : !reviewable && !progress ? (
        <p className="text-sm text-text-tertiary">State: {fix.state.replace(/_/g, ' ')}</p>
      ) : null}

      {error && <p className="text-sm text-red-600">{error}</p>}
    </div>
  )
}
