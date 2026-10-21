import { Bot, Loader2, ShieldAlert, UserCheck, Users } from 'lucide-react'
import type { FixSummary } from '../api/types'

type Props = { summary: FixSummary | undefined; t0Busy: boolean; onApproveT0: () => void; onOpenQuarantine: () => void }

export default function TierStrip({ summary, t0Busy, onApproveT0, onOpenQuarantine }: Props) {
  const t0 = summary?.tiers.T0.ready ?? 0
  const t1 = summary?.tiers.T1.to_review ?? 0
  const t2 = summary?.tiers.T2.to_review ?? 0
  const q = summary?.quarantined ?? 0
  return (
    <div className="grid lg:grid-cols-3 gap-4">
      <div className="card p-5 space-y-3">
        <div className="flex items-center gap-2">
          <Bot className="w-4 h-4 text-green-700" />
          <p className="text-xs font-semibold tracking-wider"><span className="tier t0 mr-1">T0</span> · AUTOMATED · daily</p>
        </div>
        <p className="text-sm text-text-secondary">schema, JSON-LD, fact tables, llms.txt, alt text; facts must match UC exactly</p>
        <div className="flex items-center flex-wrap gap-2">
          <span className="text-2xl font-semibold tabular-nums">{t0} ready</span>
          {summary?.review_mode && <span className="badge b-warning"><span className="dot" />Demo: review mode</span>}
        </div>
        <p className="text-xs text-text-tertiary">Would auto-publish in production</p>
        <button type="button" className="btn btn-primary" onClick={onApproveT0} disabled={t0 === 0 || t0Busy}>
          {t0Busy && <Loader2 className="w-4 h-4 animate-spin" />}
          Approve all T0
        </button>
      </div>

      <div className="card p-5 space-y-3">
        <div className="flex items-center gap-2">
          <UserCheck className="w-4 h-4 text-blue-700" />
          <p className="text-xs font-semibold tracking-wider"><span className="tier t1 mr-1">T1</span> · MARKETER REVIEW</p>
        </div>
        <p className="text-sm text-text-secondary">owned page copy, new FAQ, answer and moment pages</p>
        <span className="text-2xl font-semibold tabular-nums block">{t1} to review</span>
      </div>

      <div className="card p-5 space-y-3">
        <div className="flex items-center gap-2">
          <Users className="w-4 h-4 text-amber-700" />
          <p className="text-xs font-semibold tracking-wider"><span className="tier t2 mr-1">T2</span> · SPECIALIST REVIEW</p>
        </div>
        <p className="text-sm text-text-secondary">anything naming a real person (athlete moments), third-party corrections, community replies</p>
        <div className="flex items-center flex-wrap gap-3">
          <span className="text-2xl font-semibold tabular-nums">{t2} to review</span>
          {q > 0 && (
            <button type="button" onClick={onOpenQuarantine}
              className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold bg-red-50 text-red-700 hover:ring-1 hover:ring-red-600">
              <ShieldAlert className="w-3.5 h-3.5" />{q} quarantined
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
