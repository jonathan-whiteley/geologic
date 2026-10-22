import { useEffect, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, Check, Sparkles, X } from 'lucide-react'
import { api } from '../api/client'
import type { AnswerT, CitedDoc } from '../api/types'
import { CLUSTERS } from '../components/Heatmap'
import { PageSkeleton, ErrorRetry } from '../components/PageState'
import { MomentChip, PriorityBadge } from '../components/PromptTable'
import ClaimChip from '../components/ClaimChip'
import CitationChip from '../components/CitationChip'
import { cleanAnswer, engineRank, formatK } from '../lib/format'
import { useGeniePanel } from '../state/genie-panel'

const CLUSTER_LABEL = new Map(CLUSTERS)
const TOKEN = /\[([\w ,.-]+)\]/g

/** The answer with each [doc_id] token replaced by an inline citation chip. */
function renderAnswer(raw: string, cited: CitedDoc[]): ReactNode[] {
  const byId = new Map(cited.map(c => [c.doc_id, c]))
  const out: ReactNode[] = []
  let last = 0
  let i = 0
  for (const m of raw.matchAll(TOKEN)) {
    const text = cleanAnswer(raw.slice(last, m.index))
    if (text) out.push(<span key={`t${i}`}>{text} </span>)
    for (const id of m[1].split(',').map(x => x.trim()).filter(Boolean)) {
      const doc = byId.get(id)
      out.push(
        <span key={`c${i}-${id}`} className="mr-1">
          {doc ? <CitationChip doc={doc} /> : <span className="font-mono text-[11px] px-1.5 py-0.5 rounded-md bg-gray-100 text-gray-700">{id}</span>}
        </span>,
      )
    }
    last = (m.index ?? 0) + m[0].length
    i += 1
  }
  const tail = cleanAnswer(raw.slice(last))
  if (tail) out.push(<span key="tail">{tail}</span>)
  return out
}

function AnswerCard({ a }: { a: AnswerT }) {
  const named = !!a.lce_mentioned
  return (
    <div className="card p-4 space-y-3 flex flex-col">
      <div className="flex items-center justify-between gap-2">
        <span className="font-semibold">{a.engine}</span>
        <span className={`text-xs font-semibold ${named ? 'text-green-700' : 'text-red-700'}`}>{named ? (a.lce_rank ? `Named #${a.lce_rank}` : 'Named') : 'Not named'}</span>
      </div>
      <p className={`flex items-center gap-1.5 text-xs ${a.owned_retrieved ? 'text-green-700' : 'text-text-tertiary'}`}>
        {a.owned_retrieved ? <Check className="w-3.5 h-3.5" /> : <X className="w-3.5 h-3.5" />}
        Retrieved our page
      </p>
      <p className="text-sm leading-relaxed flex-1">
        {a.status !== 'ok' || !a.answer ? <span className="text-text-tertiary">No answer captured ({a.status}).</span> : renderAnswer(a.answer, a.cited)}
      </p>
      {a.claims.length > 0 && (
        <div className="flex flex-wrap gap-1 pt-2 border-t border-gray-100">{a.claims.map(c => <ClaimChip key={c.claim_id} claim={c} />)}</div>
      )}
    </div>
  )
}

export default function PromptDetailPage() {
  const { promptId = '' } = useParams()
  const { data, isLoading, isError, refetch, error } = useQuery({ queryKey: ['prompt', promptId], queryFn: () => api.prompt(promptId), retry: false })
  const { ask, setFocus } = useGeniePanel()

  useEffect(() => {
    setFocus(data?.prompt_text ?? null)
    return () => setFocus(null)
  }, [data?.prompt_text, setFocus])

  const back = (
    <Link to="/measure/prompts" className="inline-flex items-center gap-1.5 text-sm text-text-secondary hover:text-text-primary">
      <ArrowLeft className="w-4 h-4" />Prompt Bank
    </Link>
  )

  if (isLoading) return <div className="space-y-4">{back}<PageSkeleton /></div>
  if (isError || !data) {
    const notFound = (error as { status?: number } | null)?.status === 404
    return <div className="space-y-4">{back}<ErrorRetry message={notFound ? 'This prompt is not tracked.' : "Couldn't load this prompt."} onRetry={() => refetch()} /></div>
  }

  const answers = [...data.answers].sort((x, y) => engineRank(x.engine) - engineRank(y.engine))

  return (
    <div className="space-y-6 animate-fade-in">
      {back}
      <div className="flex items-start justify-between flex-wrap gap-4">
        <div className="space-y-2">
          <h2 className="text-2xl font-semibold">{data.prompt_text}</h2>
          <div className="flex flex-wrap items-center gap-2 text-sm text-text-secondary">
            <span className="badge b-default">{CLUSTER_LABEL.get(data.cluster) ?? data.cluster}</span>
            <PriorityBadge priority={data.priority} />
            <span>Est. monthly searches {data.est_monthly_searches != null ? formatK(data.est_monthly_searches) : 'N/A'}</span>
            {data.moment_title && <MomentChip title={data.moment_title} />}
          </div>
        </div>
        <button type="button" className="btn btn-ghost !text-xs" onClick={() => ask("How has this prompt's answer changed over time?")}>
          <Sparkles className="w-3.5 h-3.5" />Ask Genie about this prompt
        </button>
      </div>
      <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4 items-stretch">
        {answers.map(a => <AnswerCard key={a.engine} a={a} />)}
      </div>
    </div>
  )
}
