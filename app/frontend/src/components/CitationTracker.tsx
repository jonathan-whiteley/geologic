import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../api/client'
import { formatTime } from '../lib/format'
import { useTheme } from '../theme/ThemeContext'

/** Citations of one patched page per probe run, and which prompts cite it in the latest run. */
export default function CitationTracker({ pages }: { pages: { doc_id: string; label: string }[] }) {
  const { chart } = useTheme()
  const [docId, setDocId] = useState<string | undefined>(pages[0]?.doc_id)
  const current = pages.find(p => p.doc_id === docId)?.doc_id ?? pages[0]?.doc_id
  const runs = useQuery({ queryKey: ['impact', 'citations', current], queryFn: () => api.docCitations(current as string), enabled: !!current })
  const prompts = useQuery({ queryKey: ['prompts'], queryFn: api.prompts, enabled: !!current })

  if (!current) return <p className="text-sm text-text-tertiary">No patched pages yet.</p>

  const data = [...(runs.data ?? [])].sort((a, b) => a.started_at.localeCompare(b.started_at))
    .map(r => ({ ...r, label: `${new Date(r.started_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} ${formatTime(r.started_at)}` }))
  const latest = data[data.length - 1]
  const textById = new Map((prompts.data ?? []).map(p => [p.prompt_id, p.prompt_text]))

  return (
    <div className="space-y-3 pt-4 border-t border-gray-100">
      <div className="flex items-center gap-2 flex-wrap">
        <p className="text-sm font-semibold flex-1">Citations of a patched page</p>
        <select aria-label="Patched page" className="rounded-lg border border-gray-200 bg-surface px-2 py-1 text-sm"
          value={current} onChange={e => setDocId(e.target.value)}>
          {pages.map(p => <option key={p.doc_id} value={p.doc_id}>{p.label}</option>)}
        </select>
      </div>
      {runs.isError ? <p className="text-sm text-red-600">Couldn&apos;t load citations.</p> : (
        <div className="h-[160px]">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid stroke={chart.gridColor} vertical={false} />
              <XAxis dataKey="label" tick={{ fontSize: 10, fill: chart.tickColor }} axisLine={false} tickLine={false} />
              <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: chart.tickColor }} axisLine={false} tickLine={false} width={28} />
              <Tooltip content={({ active, payload }) => {
                if (!active || !payload?.length) return null
                const r = payload[0].payload as { label: string; citations: number; prompts: number }
                return <div className="custom-tooltip text-xs"><p className="text-text-secondary">{r.label}</p><p className="font-medium">{r.citations} citations · {r.prompts} prompts</p></div>
              }} />
              <Line type="monotone" dataKey="citations" stroke={chart.orange} strokeWidth={2.5} dot={{ r: 3, fill: chart.orange }} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
      {latest && (
        <div className="text-xs space-y-1">
          <p className="text-text-secondary">Cited on {latest.prompts} prompts in the latest run:</p>
          <ul className="list-disc pl-4 text-text-secondary">
            {latest.prompt_ids.map(id => <li key={id}>{textById.get(id) ?? id}</li>)}
          </ul>
        </div>
      )}
    </div>
  )
}
