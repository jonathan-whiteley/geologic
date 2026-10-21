import { Database } from 'lucide-react'
import type { FactRow } from '../api/types'

export default function FactTable({ facts, ucTable }: { facts: FactRow[]; ucTable: string }) {
  return (
    <div className="space-y-3">
      {facts.length === 0 ? (
        <p className="text-sm text-text-tertiary">No matching facts in Unity Catalog.</p>
      ) : (
        <div className="divide-y divide-gray-100 rounded-xl border border-gray-100">
          {facts.map(f => (
            <div key={f.fact_id} className={`flex flex-wrap items-center gap-3 px-3 py-2.5 text-sm ${f.current ? '' : 'text-text-tertiary'}`}>
              <span className={`font-mono text-[11px] font-semibold px-1.5 py-0.5 rounded-md ${f.current ? 'bg-green-50 text-green-700' : 'bg-gray-100 text-gray-600'}`}>{f.fact_id}</span>
              <span className={`flex-1 min-w-[140px] ${f.current ? '' : 'line-through'}`}>{f.subject_name} {f.attribute.replace(/_/g, ' ')}</span>
              <span className={`font-mono font-semibold ${f.current ? '' : 'line-through'}`}>{f.value}</span>
              <span className="text-xs text-text-tertiary">since {f.valid_from}{f.valid_to ? ` · until ${f.valid_to}` : ''}</span>
              {!f.current && <span className="text-[11px] font-medium text-text-tertiary">superseded</span>}
            </div>
          ))}
        </div>
      )}
      <span className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium bg-blue-50 text-blue-700">
        <Database className="w-3.5 h-3.5" />Unity Catalog: {ucTable}
      </span>
    </div>
  )
}
