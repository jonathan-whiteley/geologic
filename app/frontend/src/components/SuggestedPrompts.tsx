import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ChevronDown, Lightbulb, Sparkles } from 'lucide-react'
import { api } from '../api/client'
import type { PromptSuggestion } from '../api/types'
import EngineScorecard from './EngineScorecard'
import { TrackingNote, useTrackPrompt } from './AskAnything'

function SuggestionRow({ s }: { s: PromptSuggestion }) {
  const tracker = useTrackPrompt()
  const moment = s.source === 'moment'
  return (
    <div className="py-3 space-y-3">
      <div className="flex items-center gap-3 flex-wrap">
        <span className={`badge ${moment ? 'bg-orange-100 text-orange-600' : 'b-default'}`}>{moment ? 'Moment' : 'Candidate'}</span>
        <p className="text-sm flex-1 min-w-[200px]">{s.prompt_text}</p>
        {tracker.result ? (
          <Link to={`/measure/prompts/${tracker.result.prompt_id}`} className="text-sm font-medium text-green-700 hover:underline">Tracking</Link>
        ) : tracker.tracking ? <TrackingNote /> : (
          <button type="button" className="btn btn-secondary !py-1.5" onClick={() => tracker.track(s.prompt_text, s.suggestion_id)}>
            <Sparkles className="w-4 h-4 text-lce-orange" />Track and run now
          </button>
        )}
      </div>
      {tracker.error && <p className="text-sm text-red-600">{tracker.error}</p>}
      {tracker.result && <EngineScorecard answers={tracker.result.scorecard} />}
    </div>
  )
}

export default function SuggestedPrompts() {
  const [open, setOpen] = useState(false)
  const { data } = useQuery({ queryKey: ['prompt-suggestions'], queryFn: api.promptSuggestions })
  const rows = data ?? []
  return (
    <div className="card p-6">
      <button type="button" className="w-full flex items-center gap-3 text-left" aria-expanded={open} onClick={() => setOpen(v => !v)}>
        <div className="icon-tile"><Lightbulb className="w-5 h-5" /></div>
        <h3 className="font-semibold flex-1">Suggested to track ({rows.length})</h3>
        <ChevronDown className={`w-5 h-5 text-text-secondary transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <div className="mt-3 divide-y divide-gray-100">
          {rows.map(s => <SuggestionRow key={s.suggestion_id} s={s} />)}
          {rows.length === 0 && <p className="text-sm text-text-tertiary py-4">Nothing suggested right now.</p>}
        </div>
      )}
    </div>
  )
}
