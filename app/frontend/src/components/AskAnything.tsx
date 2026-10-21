import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { Loader2, Search, Sparkles } from 'lucide-react'
import { api } from '../api/client'
import type { SearchResp, TrackResp } from '../api/types'
import { useToast } from './Toast'
import EngineScorecard from './EngineScorecard'

const pct = (score: number) => Math.round(score * 100)

/** Track a new prompt and ask the four engines (15 to 20 s); refreshes the prompt table and the summary. */
export function useTrackPrompt() {
  const queryClient = useQueryClient()
  const toast = useToast()
  const [tracking, setTracking] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<TrackResp | null>(null)

  async function track(text: string, suggestionId?: string) {
    setTracking(true)
    setError(null)
    try {
      const res = await api.trackPrompt(text, suggestionId)
      setResult(res)
      toast(`Now tracking: ${res.prompt_text}`)
      queryClient.invalidateQueries({ queryKey: ['prompts'] })
      queryClient.invalidateQueries({ queryKey: ['model'] })
      queryClient.invalidateQueries({ queryKey: ['prompt-suggestions'] })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong.')
    } finally {
      setTracking(false)
    }
  }

  return { track, tracking, error, result, clear: () => { setResult(null); setError(null) } }
}

export function TrackingNote() {
  return (
    <p className="flex items-center gap-2 text-sm text-text-secondary">
      <Loader2 className="w-4 h-4 animate-spin text-lce-orange" />
      Asking 4 engines through AI Gateway...
    </p>
  )
}

export default function AskAnything() {
  const [q, setQ] = useState('')
  const [searching, setSearching] = useState(false)
  const [searchError, setSearchError] = useState<string | null>(null)
  const [res, setRes] = useState<SearchResp | null>(null)
  const tracker = useTrackPrompt()

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setSearching(true)
    setSearchError(null)
    setRes(null)
    tracker.clear()
    try {
      setRes(await api.search(q))
    } catch (err) {
      setSearchError(err instanceof Error ? err.message : 'Something went wrong.')
    } finally {
      setSearching(false)
    }
  }

  return (
    <div className="card p-6 space-y-4">
      <div className="flex items-center gap-3">
        <div className="icon-tile"><Search className="w-5 h-5" /></div>
        <div>
          <h3 className="font-semibold">Ask anything</h3>
          <p className="text-sm text-text-secondary">Type any customer question. We match it to a tracked prompt.</p>
        </div>
      </div>
      <form className="flex gap-3 flex-wrap" onSubmit={onSubmit}>
        <input
          aria-label="Ask anything"
          className="flex-1 min-w-[260px] rounded-xl border border-gray-200 bg-surface px-4 py-3 text-sm focus:border-lce-orange"
          value={q}
          maxLength={400}
          onChange={e => setQ(e.target.value)}
          placeholder="What should I order for a Super Bowl party for 12?"
        />
        <button type="submit" className="btn btn-primary !px-5" disabled={searching || tracker.tracking}>
          {searching ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
          Search
        </button>
      </form>

      {searching && <p className="text-sm text-text-secondary">Matching your question...</p>}
      {searchError && <p className="text-sm text-red-600">{searchError}</p>}

      {res && res.match && (
        <div className="space-y-3">
          <p className="text-sm">
            <span className="font-semibold text-green-700">{pct(res.match.score)}% match: </span>
            <Link to={`/measure/prompts/${res.match.prompt_id}`} className="font-medium text-lce-orange-dark hover:underline">{res.match.prompt_text}</Link>
          </p>
          <EngineScorecard answers={res.scorecard ?? []} />
        </div>
      )}

      {res && !res.match && !tracker.result && (
        <div className="rounded-xl border border-gray-100 bg-surface-secondary p-4 space-y-3">
          <p className="text-sm font-medium">Not tracked yet.</p>
          {res.nearest && (
            <p className="text-sm text-text-secondary">Closest: {res.nearest.prompt_text} ({pct(res.nearest.score)}%)</p>
          )}
          {tracker.tracking ? <TrackingNote /> : (
            <button type="button" className="btn btn-primary" onClick={() => tracker.track(res.query)}>
              <Sparkles className="w-4 h-4" />Track and run now
            </button>
          )}
          {tracker.error && <p className="text-sm text-red-600">{tracker.error}</p>}
        </div>
      )}

      {tracker.result && (
        <div className="space-y-3">
          <p className="text-sm">
            <span className="font-semibold text-green-700">Now tracking: </span>
            <Link to={`/measure/prompts/${tracker.result.prompt_id}`} className="font-medium text-lce-orange-dark hover:underline">{tracker.result.prompt_text}</Link>
            <span className="text-text-tertiary"> · {Math.round(tracker.result.elapsed_s)}s</span>
          </p>
          <EngineScorecard answers={tracker.result.scorecard} />
        </div>
      )}
    </div>
  )
}
