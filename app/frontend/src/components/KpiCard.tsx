import type { ReactNode } from 'react'

type KpiCardProps = { icon: ReactNode; label: string; value: string; subtitle?: string; sub?: ReactNode; title?: string }

export default function KpiCard({ icon, label, value, subtitle, sub, title }: KpiCardProps) {
  return (
    <div className="card p-6 card-hover relative overflow-hidden" title={title}>
      <div className="absolute top-0 right-0 w-24 h-24 opacity-5">
        <div className="w-full h-full rounded-full bg-lce-orange translate-x-8 -translate-y-8" />
      </div>
      <div className="relative">
        <div className="icon-tile mb-3">{icon}</div>
        <p className="text-sm text-text-secondary">{label}</p>
        {subtitle && <p className="text-xs text-text-tertiary">{subtitle}</p>}
        <p className="text-2xl font-semibold tabular-nums mt-1">{value}</p>
        {sub && <div className="flex flex-wrap items-center gap-2 mt-2 text-xs text-text-tertiary">{sub}</div>}
      </div>
    </div>
  )
}
